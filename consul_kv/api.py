import socket
from base64 import b64decode, b64encode
from json import loads, dumps
from logging import getLogger
from os.path import join
from urllib import request

from consul_kv.settings import DEFAULT_KV_ENDPOINT, DEFAULT_TXN_ENDPOINT

log = getLogger(__name__)


def put_kv(k, v, endpoint=DEFAULT_KV_ENDPOINT, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
    """
    Put a key and value to the distributed key value store at the location path
    :param str k: the key to put
    :param str v: the value to put
    :param str endpoint: API url to PUT to
    :param int timeout: Seconds before timing out
    :return None:
    """
    encoded = str.encode(str(v))
    url = join(endpoint, k)
    req = request.Request(
        url=url, data=encoded, method='PUT'
    )
    with request.urlopen(req, timeout=timeout) as f:
        log.debug("PUT k v pair ({}, {}) to {}: {}, {}".format(
            k, v, url, f.status, f.reason
        ))


def _mapping_to_txn_data(mapping, verb='set'):
    """
    Transform a key value mapping to a list of operations to perform
    inside the atomic transaction.
    :param dict mapping: flat dict of key/values put
    :param str verb: The type of operation to perform. See the list of possibilities
    here https://www.consul.io/docs/agent/http/kv.html#txn
    :param int timeout: Seconds before timing out
    :return list[dict, ..] txn_data: List of dicts describing the operations to perform
    """
    return [
        {
            'KV': {
                'Verb': verb,
                'Key': k,
                'Value': b64encode(str(v).encode('utf-8')).decode('utf-8'),
            }
        } for k, v in mapping.items()
    ]


def put_kv_txn(mapping, endpoint=DEFAULT_TXN_ENDPOINT, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
    """
    Update multiple keys inside a single, atomic transaction.
    The body of the request should be a list of operations to
    perform inside the atomic transaction. Up to 64 operations
    may be present in a single transaction. Each Base64-encoded
    blob of data can not be larger than 512kB.
    https://www.consul.io/docs/agent/http/kv.html
    :param dict mapping: flat dict of key/values put
    :param str endpoint: API url to PUT to. Should be a txn endpoint.
    :param int timeout: Seconds before timing out
    :return None:
    """
    txn_data = _mapping_to_txn_data(mapping, verb='set')
    data = dumps(txn_data).encode('utf-8')
    req = request.Request(
        url=endpoint, data=data, method='PUT',
        headers={'Content-Type': 'application/json'}
    )
    with request.urlopen(req, timeout=timeout) as f:
        log.debug("PUT k v mapping {} to {}: {}, {}".format(
            mapping, endpoint, f.status, f.reason
        ))


def get_kv(k=None, recurse=False, endpoint=DEFAULT_KV_ENDPOINT, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
    """
    Get the key value mapping from the distributed key value store
    :param str k: key to get
    :param bool recurse: whether or not to recurse over the path and
    retrieve all nested values
    :param str endpoint: API url to get the value from
    :param int timeout: Seconds before timing out
    :return dict mapping: key value mapping
    """
    url = join(endpoint, k) if k else endpoint
    req = request.Request(
        url=join(url, '?recurse') if recurse else url,
        method='GET'
    )
    with request.urlopen(req, timeout=timeout) as r:
        result = loads(r.read().decode('utf-8'))
    mapping = {
        # values are stored base64 encoded in consul, they
        # are decoded before returned by this function.
        r['Key']: b64decode(r['Value']).decode('utf-8')
        if r['Value'] else None for r in result if r['Key']
    }
    return mapping


def delete_kv(k=None, recurse=False, endpoint=DEFAULT_KV_ENDPOINT, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
    """
    Delete a key from the distributed key value store
    :param str k: the key to delete
    :param bool recurse: recurse the path and delete all entries
    :param str endpoint: API url to DELETE
    :param int timeout: Seconds before timing out
    :return:
    """
    url = join(endpoint, k) if k else endpoint
    req = request.Request(
        url=join(url, '?recurse') if recurse else url,
        method='DELETE'
    )
    with request.urlopen(req, timeout=timeout) as f:
        log.debug("DELETEd key {}{}: {} {}".format(
            url,
            ' recursively' if recurse else '',
            f.status,
            f.reason
        ))
