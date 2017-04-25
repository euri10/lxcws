import contextlib
import os
import pathlib
import re
import subprocess
import tempfile

import logging
import lxc

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.DEBUG)


def pull_file(container: str, guestfile: str, hostfile: str, **kwargs) -> int:
    """
    Humble attempt at running the command:
    lxc-attach -n guest -- cat guestfile > hostfile
    which cat a file on a guest container into a host file
    :param container: the container name
    :param hostfile: the host file name
    :param guestfile: the guest file name
    :param kwargs:
    :return: the exit code of the process
    """
    catfile = run_cmd(container, ['cat', guestfile], stdout=hostfile.file,
                      **kwargs)
    return catfile


def push_file(container: str, hostfile: str, guestfile: str, **kwargs) -> int:
    """
    Humble attempt at running the command:
    cat hostfile | lxc-attach -n guest -- sh -c 'exec cat > guestfile'
    which cat a file on the host then pipes it into the guest into guestfile
    with some exec magic...
    :param container: the container name
    :param hostfile: the host file name
    :param guestfile: the guest file name
    :param kwargs:
    :return: the exit code of the process
    """
    catfile = subprocess.Popen(['cat', hostfile], stdout=subprocess.PIPE)
    exec_command = 'exec cat > ' + guestfile
    return run_cmd(container, ['sh', '-c', exec_command], stdin=catfile.stdout,
                   **kwargs)


def run_cmd(container: str, command: list, env: dict = {}, **kwargs) -> int:
    """
    Run a generic command in the guest container
    :param container: the container name
    :param command: the host file name
    :param env: extra env parameters to pass
    :param kwargs: other keyword arguments you mnight want to pass,
    for a more detailed list of possibles, see:
    https://github.com/lxc/lxc/blob/master/src/python-lxc/lxc.c#L222-L225
    :return: the exit code of the process
    """
    env['LANG'] = 'C.UTF-8'
    env['TERM'] = 'xterm'
    env = ['%s=%s' % (key, value) for key, value in env.items()]
    return container.attach_wait(
        lxc.attach_run_command, command,
        extra_env_vars=env, env_policy=lxc.LXC_ATTACH_CLEAR_ENV, **kwargs)


@contextlib.contextmanager
def patch_from_template(fp: str, change: dict={}):
    """
    Edit a template file fp by changing the keys of the change dictionary
    into their values
    The template is a text file, and the function will change any occurence of
    {{KEY}} into VALUE
    :param fp: the file name
    :param change: a dictionary of the changes
    :yield: a temporary file
    """
    try:
        with tempfile.NamedTemporaryFile(mode='w+t', delete=False) as tmp:
            with open(fp) as inp:
                lines = inp.readlines()
                outlines = lines
                for i, l in enumerate(lines):
                    for k, v in change.items():
                        pattern = '({{' + k + '}})'
                        matches = re.finditer(pattern, l)
                        if matches is not None:
                            replace = v
                            outlines[i] = re.sub(pattern, replace, outlines[i])
            logger.debug('going to write {} lines'.format(len(outlines)))
            tmp.writelines(outlines)
            f = pathlib.Path(tmp.name)
            logger.debug('try {}'.format(f.exists()))
            tmp.seek(0)  # important in that with with with
            yield tmp
    finally:
        tmp.close()  # closes the file, so we can right remove it
        os.remove(tmp.name)
        logger.debug('finally {}'.format(f.exists()))


def find_and_replace(container_name: str, original_file: str, to_change: dict):
    """
    humble attempt to change original config file on guest
    :param original_phpini: the path of the oringianl file in the container
    :param tmp_phpini: the path of the temp file on host
    :param to_change: a dict of KEYS that will be changed to VALUES
    :return:
    """
    with tempfile.NamedTemporaryFile() as tmp_file:
        pull_file(container_name, original_file, tmp_file)
        with open(tmp_file.name) as tmp:
            tmp_lines = tmp.readlines()
            out_lines = []
            with tempfile.NamedTemporaryFile() as out_tmp:
                for tmp_line in tmp_lines:
                    changed = False
                    for tc in to_change.keys():
                        if re.match(tc, tmp_line) is not None:
                            nl = re.sub(tc, to_change[tc], tmp_line)
                            changed = True
                    if changed:
                        out_lines.append(nl.encode('utf-8'))
                    else:
                        out_lines.append(tmp_line.encode('utf-8'))
                for out_line in out_lines:
                    out_tmp.write(out_line)
                out_tmp.flush()
                push_file(container_name, out_tmp.name, original_file)
