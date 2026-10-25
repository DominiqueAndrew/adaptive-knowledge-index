"""Offline observational trace audit. Never execute trace commands.

Cache models here are diagnostic accounting only, not a retrieval implementation.
Observation equality is checked after the fact and is not correctness feedback.
"""
from collections import Counter, OrderedDict
import hashlib
import json
import posixpath
import re
import shlex


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def literal_read(command):
    """Narrow syntactic screen, not proof of shell/environment purity.

No expansion, redirection, arbitrary sed program, find action, or interpreter.
All arguments remain data; this function never invokes a shell.
"""
    if not isinstance(command, str) or any(c in command for c in ('$','`','\n','\r')):
        return False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|<>')
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return False
    segments, current = [], []
    for token in tokens:
        if token in ('&&', '|'):
            if not current: return False
            segments.append(current); current = []
        elif token and all(c in ';&|<>' for c in token):
            return False
        else:
            current.append(token)
    if not current: return False
    segments.append(current)
    for args in segments:
        name = args[0]
        if name == 'cd':
            if len(args) != 2 or not args[1].startswith('/') or '..' in args[1].split('/'):
                return False
        elif name in ('cat','head','tail','wc','ls','pwd','grep'):
            pass
        elif name == 'rg':
            # --pre launches a process; other uncommon modes remain opaque.
            allowed = {'-n','-i','-l','-w','-v','-F','-e','--files','--hidden','--glob','-g','--'}
            if any(a.startswith('-') and a not in allowed for a in args[1:]): return False
        elif name == 'sed':
            if len(args) != 4 or args[1] != '-n' or not re.fullmatch(r'\d+(,\d+)?p', args[2]):
                return False
        else:
            return False
    return True


def numbered_lines(response):
    """Read OpenHands cat-n observations; keep exact text after numeric prefix."""
    lines = {}
    for line in response.split('\n'):
        # OpenHands may append this wrapper to a partially clipped source line.
        # It is not source evidence; even its prefix is incomplete.
        if '<response clipped>' in line or '<NOTE>' in line:
            continue
        match = re.match(r'^\s*([1-9][0-9]*)\t(.*)$', line)
        if match:
            number, text = int(match[1]), match[2]
            if number in lines: return {}  # ambiguous output, not a single file view
            lines[number] = text
    return lines


def audit_shell_repeats(row, *, budget=256*1024):
    """Exact read-command reuse, conservatively reset by edits/opaque execution.

    Only commands with an explicit absolute `cd PATH &&` prefix are eligible:
    ambient working-directory identity is not supplied by this trace format.
    This is separate from the view LRU. Failed cd and shell aliases remain an
    observational limitation; this is not a serving cache.
    """
    counts = Counter()
    exact, lru, resident = {}, OrderedDict(), 0
    responses = {m.get('tool_call_id'): m.get('content') or ''
                 for m in row['trajectory'] if m['role'] == 'tool'}
    for message in row['trajectory']:
        calls = message.get('tool_calls') or []
        if len(calls) > 1:
            exact.clear(); lru.clear(); resident = 0
        for call in calls:
            f = call['function']; name = f['name']
            try: args = json.loads(f['arguments'])
            except (ValueError, TypeError): args = {}
            if name in ('think','task_tracker','finish'): continue
            if name == 'str_replace_editor' and args.get('command') == 'view': continue
            command = args.get('command', '')
            if name != 'execute_bash' or not literal_read(command) or args.get('is_input') in (True,'true'):
                exact.clear(); lru.clear(); resident = 0
                counts['boundaries'] += 1; continue
            counts['literal_read_calls'] += 1
            prefix = re.match(r'^\s*cd\s+(/[^\s;&|]+)\s*&&\s*(.+)$', command)
            if not prefix or re.search(r'(^|[&|]\s*)\s*cd\s', prefix[2]):
                counts['ambient_cwd_excluded'] += 1; continue
            response = responses.get(call['id'])
            if response is None:
                counts['missing_response'] += 1; continue
            counts['eligible_calls'] += 1
            size = len(response.encode()); value = digest(response), size
            counts['response_bytes'] += size
            lexical = bool(re.search(r'(^|[&|]\s*)\s*(grep|rg)\s', prefix[2]))
            counts['lexical_calls'] += int(lexical)
            counts['lexical_response_bytes'] += size if lexical else 0
            if command in exact:
                if exact[command][0] == value[0]:
                    counts['exact_equal_hits'] += 1
                    counts['exact_equal_response_bytes'] += size
                    counts['lexical_exact_equal_hits'] += int(lexical)
                    counts['lexical_exact_equal_response_bytes'] += size if lexical else 0
                else: counts['exact_observation_mismatches'] += 1
            if command in lru:
                if lru[command][0] == value[0]:
                    counts['lru_equal_hits'] += 1
                    counts['lru_equal_response_bytes'] += size
                resident -= lru.pop(command)[1]
            exact[command] = value
            if size <= budget:
                while lru and resident + size > budget:
                    resident -= lru.popitem(last=False)[1][1]
                    counts['lru_evictions'] += 1
                lru[command] = value; resident += size
            counts['peak_lru_bytes'] = max(counts['peak_lru_bytes'], resident)
            assert resident <= budget
    return dict(counts)


def audit_row(row, *, all_shell_barriers=False, budget=256*1024):
    counts = Counter()
    functions = Counter()
    boundaries = Counter()
    exact = {}             # unlimited exact file-view result memoization
    lru = OrderedDict()    # same results, bounded by serialized response UTF8 bytes
    line_cache = {}        # unlimited observed numbered-line memoization
    resident = 0
    responses = {m.get('tool_call_id'): m.get('content') or ''
                 for m in row['trajectory'] if m['role'] == 'tool'}

    def invalidate(path=None):
        nonlocal resident
        for key in list(exact):
            if path is None or key[0] == path: del exact[key]
        for key in list(lru):
            if path is None or key[0] == path:
                resident -= lru.pop(key)[1]
        if path is None: line_cache.clear()
        else: line_cache.pop(path, None)

    for message in row['trajectory']:
        if message['role'] != 'assistant': continue
        calls = message.get('tool_calls') or []
        if len(calls) > 1:
            counts['multi_call_messages'] += 1
            invalidate(); boundaries['multi_call'] += 1
        for call in calls:
            function = call['function']; name = function['name']
            counts['calls'] += 1; functions[name] += 1
            try: args = json.loads(function['arguments'])
            except (ValueError, TypeError):
                invalidate(); boundaries['invalid_arguments'] += 1; continue
            if name in ('think','task_tracker','finish'): continue
            if name == 'execute_bash':
                read = literal_read(args.get('command')) and args.get('is_input') not in (True,'true')
                counts['literal_read_shell' if read else 'opaque_shell'] += 1
                if all_shell_barriers or not read:
                    invalidate(); boundaries['shell'] += 1
                continue
            if name != 'str_replace_editor':
                invalidate(); boundaries['unknown_tool'] += 1; continue
            command, path = args.get('command'), args.get('path')
            if not isinstance(path, str) or not path.startswith('/') or any(c in path for c in ('$','`','~')):
                invalidate(); boundaries['unresolved_path'] += 1; continue
            path = posixpath.normpath(path)
            if command != 'view':
                invalidate(path); boundaries['editor_mutation'] += 1; continue
            counts['view_calls'] += 1
            response = responses.get(call.get('id'))
            if response is None:
                counts['missing_view_response'] += 1; continue
            counts['view_response_bytes'] += len(response.encode())
            lines = numbered_lines(response)
            if '<response clipped>' in response:
                counts['clipped_view_responses'] += 1
            if not lines:
                counts['view_without_numbered_lines'] += 1; continue
            counts['eligible_views'] += 1
            content_bytes = sum(len(text.encode()) for text in lines.values())
            counts['numbered_line_bytes'] += content_bytes
            counts['numbered_lines'] += len(lines)
            key = (path, json.dumps(args.get('view_range'), sort_keys=True))
            value = digest(response), len(response.encode())
            hit = key in exact
            if hit and exact[key][0] == value[0]:
                counts['exact_equal_hits'] += 1
                counts['exact_equal_response_bytes'] += value[1]
            elif hit:
                counts['exact_observation_mismatches'] += 1
                invalidate(path)
            if key in lru and lru[key][0] == value[0]:
                counts['lru_equal_hits'] += 1
                counts['lru_equal_response_bytes'] += value[1]
                lru.move_to_end(key)
            stored_lines = line_cache.setdefault(path, {})
            mismatches = sum(n in stored_lines and stored_lines[n] != digest(text) for n,text in lines.items())
            if mismatches:
                counts['line_observation_mismatches'] += mismatches
                # A changed observation invalidates all prior lines of this file.
                invalidate(path); stored_lines = {}; line_cache[path] = stored_lines
            reused = [n for n,text in lines.items() if stored_lines.get(n) == digest(text)]
            reuse_bytes = sum(len(lines[n].encode()) for n in reused)
            counts['equal_overlap_lines'] += len(reused)
            counts['equal_overlap_line_bytes'] += reuse_bytes
            if len(reused) == len(lines): counts['fully_observed_views'] += 1
            if not hit:
                counts['beyond_exact_overlap_line_bytes'] += reuse_bytes
                counts['beyond_exact_overlap_lines'] += len(reused)
                if reused: counts['beyond_exact_overlap_views'] += 1
            for n,text in lines.items(): stored_lines[n] = digest(text)
            exact[key] = value
            if key in lru: resident -= lru.pop(key)[1]
            if value[1] <= budget:
                while lru and resident + value[1] > budget:
                    resident -= lru.popitem(last=False)[1][1]
                    counts['lru_evictions'] += 1
                lru[key] = value; resident += value[1]
            counts['peak_lru_bytes'] = max(counts['peak_lru_bytes'], resident)
            assert resident <= budget
    return {'trajectory_sha256': digest(row['trajectory_id']),
            'repository_sha256': digest(row['repo']), 'counts': dict(counts),
            'functions': dict(functions), 'boundaries': dict(boundaries)}
