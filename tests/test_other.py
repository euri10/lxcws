# adapted from https://stgraber.org/2014/02/05/lxc-1-0-scripting-with-the-api/
import logging
import tempfile
import lxc

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.DEBUG)

cccc = 'toto'


def test_fixture(temp_container):
    assert type(temp_container) is lxc.Container
    assert temp_container.name == cccc


def get_container_output(container, command, **kwargs):
    with tempfile.NamedTemporaryFile() as t:
        container.attach_wait(lxc.attach_run_command, command, stdout=t.file,
                              **kwargs)
        t.seek(0)
        output = t.readlines()
        return output


def test_get_container_output(temp_container):
    out = get_container_output(temp_container, ['id'])
    logger.debug(out)
    assert [b'uid=0(root) gid=0(root) groups=0(root)\n'] == out
    out = get_container_output(temp_container, ['id'], uid=1000, gid=1000)
    logger.debug(out)
    assert [b'uid=1000(ubuntu) gid=1000(ubuntu) groups=1000(ubuntu)\n'] == out
    out = get_container_output(temp_container, ['cat', '/etc/hostname'])
    logger.debug(out)
    assert [str.encode(temp_container.name)+b'\n'] == out
