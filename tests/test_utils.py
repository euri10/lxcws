import os
import tempfile
from src.utils.utils import push_file, pull_file, patch_from_template, \
    find_and_replace


TEST_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)))


def push_test(container, pushhere):
    with tempfile.NamedTemporaryFile() as t:
        t.write(b'original file on host\n2nd line\n')
        t.seek(0)
        push_here = pushhere
        return push_file(container, t.name, push_here)


def test_pull_file(temp_container):
    # push something, pull it, compare ?
    push_here = '/tmp/push'
    a = push_test(temp_container, push_here)
    assert a == 0
    rootfs = temp_container.get_config_item('lxc.rootfs')
    pushed_file = os.path.join(rootfs, push_here[1:])
    assert os.path.exists(pushed_file)
    with tempfile.NamedTemporaryFile() as destination:
        b = pull_file(temp_container, push_here, destination)
        assert b == 0
        with open(destination.name) as comp:
            comp_lines = comp.readlines()
            assert comp_lines[0] == 'original file on host\n'
            assert comp_lines[1] == '2nd line\n'


def test_push_file(temp_container):
    push_here = '/tmp/push'
    a = push_test(temp_container, push_here)
    assert a == 0
    assert 'lxc.rootfs' in temp_container.get_keys()
    rootfs = temp_container.get_config_item('lxc.rootfs')
    pushed_file = os.path.join(rootfs, push_here[1:])
    assert os.path.exists(pushed_file)
    with open(pushed_file) as pf:
        comp_lines = pf.readlines()
        assert comp_lines[0] == 'original file on host\n'
        assert comp_lines[1] == '2nd line\n'


def test_patch_from_template():
    with patch_from_template(os.path.join(TEST_TEMPLATE_DIR, 'simple'),
                             {'a': 'suba', 'b': 'subb'}) as patch_settings:
        with open('/home/lotso/PycharmProjects/lxcws/tests/simple_correct') as correct: # noqa
            correct_lines = correct.readlines()
        changed_lines = patch_settings.readlines()
        assert correct_lines == changed_lines


def test_find_and_replace(temp_container):
    push_here = '/tmp/push'
    a = push_test(temp_container, push_here)
    assert a == 0
    assert 'lxc.rootfs' in temp_container.get_keys()
    rootfs = temp_container.get_config_item('lxc.rootfs')
    pushed_file = os.path.join(rootfs, push_here[1:])
    assert os.path.exists(pushed_file)
    find_and_replace(temp_container, '/tmp/push',
                     {'original file on host': 'modified file on host'})
