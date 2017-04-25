# adapted from https://stgraber.org/2014/02/05/lxc-1-0-scripting-with-the-api/
import logging
import re
import tempfile
import lxc

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.DEBUG)


def test_fixture(temp_container):
    assert type(temp_container) is lxc.Container


def get_container_output(container, command, **kwargs):
    with tempfile.NamedTemporaryFile() as t:
        container.attach_wait(lxc.attach_run_command, command, stdout=t.file,
                              **kwargs)
        t.seek(0)
        output = t.readlines()
        print(output)
        return output


def test_keys(temp_container):
    with open(temp_container.config_file_name) as conf_file:
        lines = conf_file.readlines()
    f_config = []
    for potential_option in lines:
        m = re.match('^([^#]+) = (.*)$', potential_option)
        if m is not None:
            f_key = m.group(1)
            f_value = m.group(2)
            f_config.append((f_key, f_value))

    for k in temp_container.get_keys():
        try:
            k_accessible = temp_container.get_config_item(k)

            comp = []
            for idx, f in enumerate(f_config):
                if k == f[0]:
                    comp.append(f_config[idx][1])
            if k_accessible in comp:
                # logger.info('{} is accessible | py: {} | config: {}'.format
                pass
            else:
                # logger.info('{} is accessible | py: {} | config: {}'.format(k,k_accessible,comp)) # noqa
                pass
        except Exception as e:
            k_in_config = [f[0] == k for f in f_config]
            if True in k_in_config:
                logger.error(
                    '{} is not accessible but it is in config file'.format(k))


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
