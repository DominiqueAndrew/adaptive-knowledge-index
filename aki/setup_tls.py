"""Read-only TLS trust preflight; never downloads roots or disables verification."""
import hashlib
from pathlib import Path
import ssl


def verified_context():
    context=ssl.create_default_context()
    proof={'source':'python_default','default_ca_count':context.cert_store_stats()['x509_ca']}
    if proof['default_ca_count']==0:
        # Optional, already-installed tooling dependency. Never install it here.
        try:import certifi
        except ImportError as exc:raise RuntimeError('No default trust roots or existing certifi bundle') from exc
        bundle=Path(certifi.where())
        context=ssl.create_default_context(cafile=str(bundle))
        proof.update(source='existing_certifi',bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),
                     bundle_version=getattr(certifi,'__version__','unreported'))
    proof['loaded_ca_count']=context.cert_store_stats()['x509_ca']
    if not proof['loaded_ca_count'] or not context.check_hostname or context.verify_mode!=ssl.CERT_REQUIRED:
        raise RuntimeError('Verified hostname and nonempty CA store required')
    return context,proof
