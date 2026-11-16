"""Original TEST run bindings, supplied only by an owner's durable admission."""
from contextlib import contextmanager
from contextvars import ContextVar
import copy
import re
import uuid
from jwt import InvalidTokenError

_current = ContextVar('identity_nightly_admission', default=None)
_subjects = frozenset()
_HEX = re.compile(r'[a-f0-9]{64}')
_RUN = re.compile(r'[0-9]{1,20}-[0-9]{1,20}-(flags-(hypermesh|portal|s3rch)-browser|(portal|s3rch)-device-transfer)')


def require(value):
    if not value: raise InvalidTokenError('Original run authority required')


def configure_subjects(subjects):
    """Configure once at owner startup; no credentials or per-request settings."""
    global _subjects
    require(type(subjects) in (list, tuple, set, frozenset) and len(subjects)<=64)
    require(all(isinstance(s,str) and str(uuid.UUID(s))==s for s in subjects))
    _subjects=frozenset(subjects)


@contextmanager
def admitted_run(binding):
    """The caller must persist admission first and complete only after native work.

    This helper grants no admission and accepts no browser JSON directly. Closing
    it invalidates inherited async/thread contexts as well as the current task.
    """
    require(type(binding) is dict and binding.get('version')==1)
    require(isinstance(binding.get('run'),str) and _RUN.fullmatch(binding['run']))
    require(isinstance(binding.get('generation'),str) and _HEX.fullmatch(binding['generation']))
    scope=binding.get('scope');require(type(scope) is dict)
    require(binding['run'].endswith('-'+str(scope.get('suite'))))
    for field in ('subject','tenant'):
        require(isinstance(scope.get(field),str) and str(uuid.UUID(scope[field]))==scope[field])
    require(isinstance(binding.get('operation'),str) and str(uuid.UUID(binding['operation']))==binding['operation'])
    require(_current.get() is None)
    value={'binding':copy.deepcopy(binding),'closed':False}
    token=_current.set(value)
    try:yield
    finally:value['closed']=True;_current.reset(token)


def require_original_run(claims):
    """Call only after native signature/issuer checks, including offline paths."""
    context=_current.get();marker=claims.get('nightly_run')
    if context is None:
        require('nightly_run' not in claims and claims.get('sub') not in _subjects)
        return
    require(not context['closed'])
    binding=context['binding'];scope=binding['scope']
    require(type(marker) is dict and set(marker)=={'run','generation'}
            and marker=={key:binding[key] for key in ('run','generation')}
            and claims.get('sub')==scope['subject'])
    for key in ('tenant_id','https://spanopticon.dev/tenant_id'):
        if key in claims:require(claims[key]==scope['tenant'])


def derived_run(claims,tenant_id):
    require_original_run(claims)
    marker=claims.get('nightly_run')
    if marker is None:return {}
    require(str(tenant_id)==_current.get()['binding']['scope']['tenant'])
    return {'nightly_run':copy.deepcopy(marker)}
