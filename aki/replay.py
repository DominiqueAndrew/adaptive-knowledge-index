"""Safe data-only source-prefix reconstruction for executed-trace feasibility.

No trace command, source module, setup instruction or repository executable runs.
Returned hashes identify reconstructed snapshots, not observed live environments.
"""
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
import time
from .trace_audit import literal_read, numbered_lines


def sha(data): return hashlib.sha256(data).hexdigest()


def source_path(path, source_root='/testbed'):
    if path==source_root:return '.'
    if not isinstance(path,str) or not path.startswith(source_root+'/'):
        raise ValueError('unsupported source root')
    p=PurePosixPath(path.removeprefix(source_root+'/'))
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('unresolved source path')
    return str(p)


def view_lines(payload, view_range=None):
    """UTF8 text subset of ACI 0.3.1 view semantics, verified against observations."""
    if b'\0' in payload: raise ValueError('binary view unsupported')
    text=payload.decode('utf-8').replace('\r\n','\n').replace('\r','\n')
    start=1
    if view_range:
        if len(view_range)!=2 or not all(type(i)==int for i in view_range):raise ValueError('invalid view range')
        start,end=view_range
        physical=list(io.StringIO(text))
        if start<1 or start>len(physical) or end>len(physical) or end!=-1 and end<start:raise ValueError('invalid view range')
        if end==-1:end=len(physical)
        text='\n'.join(''.join(physical[start-1:end]).splitlines())
    clipped=len(text)>16000
    lines=text[:16000].split('\n')
    if clipped:lines=lines[:-1]  # incomplete last line receives tool notice
    return {start+i:line for i,line in enumerate(lines)}


def known_read(command):
    # Literal find predicates plus read-only pipeline stages. No find actions,
    # expansion, redirection, interpreter or execution is supported.
    if literal_read(command):return True
    if not isinstance(command,str) or any(x in command for x in ('$','`',';','>','<','\n','\r')):return False
    import shlex
    try:
        lexer=shlex.shlex(command,posix=True,punctuation_chars='&|')
        lexer.whitespace_split=True;tokens=list(lexer)
    except ValueError:return False
    segments=[];args=[]
    for token in tokens:
        if token in ('&&','|'):
            if not args:return False
            segments.append(args);args=[]
        elif token in ('&','||'):return False
        else:args.append(token)
    if not args:return False
    segments.append(args);seen_find=False
    for args in segments:
        if args[0]!='find':
            if not literal_read(shlex.join(args)):return False
            continue
        seen_find=True
        if len(args)<2 or args[1].startswith('-'):return False
        i=2
        while i<len(args):
            if args[i] in ('-name','-iname','-path','-ipath','-type','-maxdepth','-mindepth') and i+1<len(args):i+=2
            elif args[i] in ('-print','-print0','-o','-a','-not','!','(',')'):i+=1
            else:return False
    return seen_find


def reconstruct(row, root, manifest, source_root='/testbed'):
    """Replay until first unproven state transition; time matched source views."""
    reconstruction_start=time.perf_counter_ns()
    files={r['path']:r['sha256'] for r in manifest['entries'] if r['kind']=='file'}
    links={r['path']:r.get('target_sha256') for r in manifest['entries'] if r['kind']=='unfollowed-link'}
    overlay={}; events=[]; counts={}; stop=None
    responses={m.get('tool_call_id'):m.get('content') or '' for m in row['trajectory'] if m['role']=='tool'}
    def bump(name):counts[name]=counts.get(name,0)+1
    def tree_hash():
        return sha(json.dumps({'files':sorted(files.items()),'unfollowed_links':sorted(links.items())},separators=(',',':')).encode())
    initial=tree_hash(); identity=initial
    setup_ns=time.perf_counter_ns()-reconstruction_start
    for mi,message in enumerate(row['trajectory']):
        calls=message.get('tool_calls') or []
        if len(calls)>1:stop={'reason':'ambiguous_parallel_order','message_index':mi};break
        for call in calls:
            f=call['function'];name=f['name'];bump('prefix_calls')
            try:args=json.loads(f['arguments'])
            except (ValueError,TypeError):stop={'reason':'unparseable_arguments','message_index':mi};break
            if name in ('think','task_tracker','finish'):continue
            if name=='execute_bash':
                if known_read(args.get('command')) and args.get('is_input') not in (True,'true'):
                    bump('recognized_shell_reads_not_timed');continue
                stop={'reason':'opaque_shell_state_transition','message_index':mi,'command_sha256':sha(str(args.get('command')).encode())};break
            if name!='str_replace_editor':stop={'reason':'unsupported_tool','message_index':mi};break
            if args.get('command')=='view' and args.get('path')=='/workspace' and source_root.startswith('/workspace/'):
                bump('container_directory_views_not_timed');continue
            try:relative=source_path(args.get('path'), source_root)
            except ValueError:stop={'reason':'unresolved_path','message_index':mi};break
            response=responses.get(call['id'])
            if response is None:stop={'reason':'missing_tool_response','message_index':mi};break
            cmd=args.get('command')
            if relative in links:
                stop={'reason':'unfollowed_source_link','message_index':mi};break
            if cmd=='view':
                if relative not in files:
                    # Directory listing is observable but not part of file-view replay.
                    if relative=='.' or any(p.startswith(relative.rstrip('/')+'/') for p in files):
                        bump('directory_views_not_timed');continue
                    stop={'reason':'path_absent_from_declared_snapshot','message_index':mi,'path_sha256':sha(relative.encode())};break
                observed=numbered_lines(response)
                if not observed:
                    stop={'reason':'uninterpretable_view_response','message_index':mi};break
                wall=time.perf_counter_ns();cpu=time.process_time_ns()
                try:
                    payload=overlay[relative] if relative in overlay else (root/relative).read_bytes()
                    file_hash=sha(payload)
                    if file_hash!=files[relative]:raise ValueError('local source hash changed')
                    predicted=view_lines(payload,args.get('view_range'))
                except (ValueError,UnicodeError,OSError):
                    stop={'reason':'unsupported_text_or_range','message_index':mi};break
                cpu_ns=time.process_time_ns()-cpu;wall_ns=time.perf_counter_ns()-wall
                equal=predicted==observed
                events.append({'message_index':mi,'path_sha256':sha(relative.encode()),'file_sha256':file_hash,
                               'tree_sha256':identity,'view_signature_sha256':sha(json.dumps([relative,args.get('view_range')],sort_keys=True).encode()),
                               'output_sha256':sha(json.dumps(predicted,sort_keys=True).encode()),'observed_output_sha256':sha(json.dumps(observed,sort_keys=True).encode()),
                               'matched':equal,'observed_lines':len(observed),'predicted_lines':len(predicted),
                               'file_bytes':len(payload),'wall_ns':wall_ns,'cpu_ns':cpu_ns})
                if not equal:stop={'reason':'declared_source_observation_mismatch','message_index':mi};break
                bump('matched_views')
            elif cmd in ('str_replace','create'):
                try:
                    if cmd=='create':
                        if relative in files or not response.startswith('File created successfully at:'):
                            raise ValueError('create not proven')
                        changed=args['file_text'].encode('utf-8')
                    else:
                        if relative not in files or 'has been edited' not in response:raise ValueError('edit not proven')
                        before=(overlay[relative] if relative in overlay else (root/relative).read_bytes()).decode('utf-8')
                        old=args['old_str'];new=args.get('new_str','')
                        if not old or before.count(old)!=1:raise ValueError('edit precondition failed')
                        changed=before.replace(old,new,1).encode('utf-8')
                    overlay[relative]=changed;files[relative]=sha(changed);identity=tree_hash();bump('reconstructed_edits')
                except (ValueError,UnicodeError,KeyError):
                    stop={'reason':'unproven_editor_mutation','message_index':mi};break
            else:stop={'reason':'unsupported_editor_operation','message_index':mi};break
        if stop:break
    return {'initial_reconstructed_tree_sha256':initial,'reconstruction_setup_ns':setup_ns,
            'reconstruction_total_ns':time.perf_counter_ns()-reconstruction_start,
            'counts':counts,'events':events,'stop':stop,
            'qualifies':counts.get('matched_views',0)>=3 and all(e['matched'] for e in events)}
