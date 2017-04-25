import logging
import os
import tempfile

import click
import lxc

from src.utils.utils import push_file, run_cmd, patch_from_template, \
    find_and_replace

logger = logging.getLogger(__name__)
logging.basicConfig()

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            'templates')


def install_common(container_name: str, user_lxcws: str):
    """
    Install the common packages required by the supported webshops
    :param container_name: the container name
    :param user_lxcws: the desired user name that will run the webshop
    :return:
    """
    container = lxc.Container(container_name)
    if not container.defined:
        logger.debug('Container already exists')
    else:
        container.start()
        container.get_ips(timeout=30)

    run_cmd(container, ['apt-get', 'update'])
    run_cmd(container, ['apt-get', 'dist-upgrade', '-y'])
    # need perl-modules for deluser
    run_cmd(container, ['apt-get', 'install', 'perl-modules', '-y'])
    # remove default ubuntu user and previous user_lxcws installed
    run_cmd(container, ['deluser', 'ubuntu', '--remove-all-files'])
    run_cmd(container, ['deluser', user_lxcws, '--remove-all-files'])
    run_cmd(container, ['apt-get', 'install', 'wget', '-y'])

    # Create the new user account
    run_cmd(container, ['adduser', user_lxcws])


@click.group()
@click.option('--debug/--no_debug', default=True,
              help='Set to true to see debug logs on top of info')
def cli(debug):
    """
    A simple command line tool to install containers running webshops (saleor,
    oscar) and rtorrent / rutorrent. More to be added, maybe.
    I used that little project to "learn programming" containers in python,
    don't expect much more of it
    """
    if debug:
        logging.root.setLevel(level=logging.DEBUG)
    else:
        logging.root.setLevel(level=logging.INFO)


@click.command()
@click.option('--container_name', '-n', help='container name')
def create(container_name):
    """Create a container"""
    container = lxc.Container(container_name)
    if container.defined:
        logger.info('Container already exists')
    else:
        # Create the container rootfs
        if not container.create(
                'download', lxc.LXC_CREATE_QUIET,
                {'dist': 'ubuntu', 'release': 'xenial', 'arch': 'amd64'}
        ):
            logger.debug('Failed to create the container rootfs')
        else:
            logger.info('Created the container rootfs')
    # Save the configuration
    container.save_config()


@click.command()
@click.option('--container_name', '-n')
def destroy(container_name):
    """Destroy a container"""
    container = lxc.Container(container_name)
    if not container.defined:
        logger.info('Container doesn\'t exists')
    else:
        if container.running:
            container.stop()
        container.destroy()


@click.command()
@click.option('--container_name', '-n')
@click.option('--user_lxcws', '-u')
@click.option('--domain_lxcws', '-d')
def install_torrent(container_name, user_lxcws, domain_lxcws):
    """Install a rutorrent / rtorrent machine and run it"""
    container = lxc.Container(container_name)
    if not container.defined:
        logger.info('Container doesnt exists, create it running lxcws create '
                    '-n container_name')
    else:
        container.start()
        # ip = container.get_ips(timeout=30)
        install_common(container_name, user_lxcws)

        run_cmd(container, ['apt-get', 'install', 'git', '-y'])
        run_cmd(container, ['apt-get', 'install', 'rtorrent', '-y'])

        # from https://github.com/Novik/ruTorrent/wiki/NGINX---PHP-FPM---RTORRENT # noqa
        # install nginx first to get www-data group for
        # group / user creation that follows
        run_cmd(container, ['apt-get', 'install', 'nginx', '-y'])

        run_cmd(container, ['groupadd', 'rtorrent-socket'])
        run_cmd(container, ['useradd', 'rutorrent', '-M', '-s', '/bin/false'])
        for u in [user_lxcws, 'rutorrent', 'www-data']:
            run_cmd(container, ['usermod', '-aG', 'rtorrent-socket', u])

        # php config
        run_cmd(container, ['apt-get', 'install', 'php7.0-fpm', '-y'])
        find_and_replace(container, '/etc/php/7.0/fpm/php.ini',
                         {';cgi.discard_path=1': 'cgi.discard_path=1'})
        push_file(container, os.path.join(TEMPLATE_DIR,
                                          'php7.0_rutorrent.conf_template'),
                  '/etc/php/7.0/fpm/pool.d/rutorrent.conf')
        run_cmd(container, ['systemctl', 'reload-or-restart', 'php7.0-fpm'])

        # nginx config
        with patch_from_template(
                os.path.join(TEMPLATE_DIR, 'rutorrent_nginx_template'),
                {'DOMAIN': domain_lxcws, 'USER': user_lxcws}
        ) as patch_settings:
            push_file(container, patch_settings.name,
                      '/etc/nginx/sites-available/rutorrent')

        # ln -s /etc/nginx/sites-available/saleor /etc/nginx/sites-enabled/
        run_cmd(container, ['ln', '-s', '/etc/nginx/sites-available/rutorrent',
                            '/etc/nginx/sites-enabled/'])
        run_cmd(container, ['systemctl', 'reload-or-restart', 'nginx'])

        myhome = os.path.join('/home', user_lxcws)
        run_cmd(container, ['git', 'clone',
                            'https://github.com/Novik/ruTorrent'],
                uid=1000, gid=1000, initial_cwd=myhome)

        # rtorrent config:
        rtorrenrc = os.path.join(myhome, '.rtorrent.rc')
        with patch_from_template(
                os.path.join(TEMPLATE_DIR, 'rtorrent_template'),
                {'DOMAIN': domain_lxcws, 'USER': user_lxcws}
        ) as rtor:
            push_file(container, rtor.name, rtorrenrc, uid=1000, gid=1000)
        run_cmd(container, ['mkdir', '-p',
                            os.path.join(myhome, 'rtorrent', 'watch', 'load'),
                            os.path.join(myhome, 'rtorrent', 'watch', 'start'),
                            os.path.join(myhome, 'rtorrent', 'log'),
                            os.path.join(myhome, 'rtorrent', '.session'),
                            os.path.join(myhome, 'rtorrent', 'download')],
                uid=1000, gid=1000)

        # config rutorrent config.php with sockets
        configphp = os.path.join(myhome, 'ruTorrent', 'conf', 'config.php')
        socket = os.path.join(myhome, '.rtorrent.sock')
        find_and_replace(container, configphp,
                         {'\t\$scgi_port = 5000;\n': '',
                          '\t\$scgi_host = "127\.0\.0\.1";\n': '',
                          '\t// \$scgi_port = 0;\n': '\t$scgi_port = 0;\n',
                          '\t// \$scgi_host = "unix:///tmp/rpc.socket";\n':
                              '\t$scgi_host = "unix://'+socket+'";\n'})

        a = run_cmd(container, ['rtorrent'], uid=1000, gid=1000)
        print(a)


@click.command()
@click.option('--container_name', '-n')
@click.option('--user_lxcws', '-u')
@click.option('--domain_lxcws', '-d')
@click.option('--secretkey', '-s', envvar='SECRET_KEY')
@click.option('--sendgrid_username', '-sgu', envvar='SENDGRID_USERNAME')
@click.option('--sendgrid_password', '-sgu', envvar='SENDGRID_PASSWORD')
def install_saleor(container_name, user_lxcws, domain_lxcws, secretkey,
                   sendgrid_username, sendgrid_password):
    """Install a Saleor webshop and run it"""
    container = lxc.Container(container_name)
    if not container.defined:
        logger.info('Container doesnt exists, create it running lxcws create '
                    '-n container_name')
    else:
        container.start()
        # ip = container.get_ips(timeout=30)
        install_common(container_name, user_lxcws)
        run_cmd(container, ['apt-get', 'install', 'python3-virtualenv', '-y'])
        run_cmd(container, ['apt-get', 'install', 'python3-pip', '-y'])
        run_cmd(container, ['apt-get', 'install', 'git', '-y'])
        run_cmd(container, ['apt-get', 'install', 'postgresql-9.5', '-y'])
        run_cmd(container,
                ['apt-get', 'install', 'postgresql-server-dev-9.5', '-y'])
        run_cmd(container, ['apt-get', 'install', 'libffi-dev', '-y'])
        run_cmd(container, ['apt-get', 'install', 'redis-server', '-y'])

        # from: https://nodejs.org/en/download/package-manager/#debian-and-ubuntu-based-linux-distributions # noqa
        # curl -sL https://deb.nodesource.com/setup_6.x | sudo -E bash -
        # sudo apt-get install -y nodejs
        run_cmd(container, ['wget', 'https://deb.nodesource.com/setup_6.x'])
        run_cmd(container, ['chmod', '+x', 'setup_6.x'])
        run_cmd(container, ['bash', 'setup_6.x'])
        run_cmd(container, ['rm', 'setup_6.x'])
        run_cmd(container, ['apt-get', 'install', 'nodejs', '-y'])

        # from: https://yarnpkg.com/en/docs/install
        # curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | sudo apt-key add - # noqa
        # echo "deb https://dl.yarnpkg.com/debian/ stable main" | sudo tee /etc/apt/sources.list.d/yarn.list # noqa
        # sudo apt-get update && sudo apt-get install yarn
        run_cmd(container, ['wget', 'https://dl.yarnpkg.com/debian/pubkey.gpg']) # noqa
        run_cmd(container, ['apt-key', 'add', 'pubkey.gpg'])
        run_cmd(container, ['rm', 'pubkey.gpg'])
        with tempfile.NamedTemporaryFile() as t:
            t.write(b'deb https://dl.yarnpkg.com/debian/ stable main')
            t.seek(0)
            push_file(container, t.name, '/etc/apt/sources.list.d/yarn.list')
        run_cmd(container, ['apt-get', 'update'])
        run_cmd(container, ['apt-get', 'install', 'yarn', '-y'])

        # some paths to use later on
        myhome = os.path.join('/home', user_lxcws)
        saleor_dir = os.path.join(myhome, 'saleor')
        managepy = os.path.join(saleor_dir, 'manage.py')

        # clone repo
        run_cmd(container,
                ['git', 'clone', 'https://github.com/mirumee/saleor.git'],
                uid=1000, gid=1000, initial_cwd=myhome)

        # install requirements.txt
        # create postgresql saleor password and db
        run_cmd(container, ['pip3', 'install', '-r',
                            os.path.join(saleor_dir, 'requirements.txt')])
        run_cmd(container, ['dropdb', 'saleor'], uid=106, gid=112)
        run_cmd(container, ['dropuser', 'saleor'], uid=106, gid=112)
        run_cmd(container, ['createuser', 'saleor', '-s', '-P'], uid=106,
                gid=112)
        run_cmd(container, ['createdb', 'saleor', ], uid=106, gid=112)

        # env
        env = {'SECRET_KEY': secretkey, 'ALLOWED_HOSTS': domain_lxcws,
               'REDIS_URL': 'redis://127.0.0.1:6379/0',
               'SENDGRID_USERNAME': sendgrid_username,
               'SENDGRID_PASSWORD': sendgrid_password}

        # python manage.py migrate
        run_cmd(container, ['python3', managepy, 'migrate'],
                uid=1000, gid=1000, env=env)

        # yarn
        run_cmd(container, ['yarn'], uid=1000, gid=1000,
                initial_cwd=saleor_dir)
        run_cmd(container, ['npm', 'install', 'webpack', '--save-dev'],
                uid=1000, gid=1000, initial_cwd=saleor_dir)
        run_cmd(container, ['yarn', 'run', 'build-assets', ], uid=1000,
                gid=1000, initial_cwd=saleor_dir)

        # python manage.py populatedb with admin,
        # initial_cwd important as placeholders aren't located correctly
        # if not set
        run_cmd(container,
                ['python3', managepy, 'populatedb', '--createsuperuser'],
                uid=1000,
                gid=1000, env=env, initial_cwd=saleor_dir)

        # nginx configuration
        # requires a reverse proxy on host of course, lxc container ip adjusted
        # on example found in templates/nginx_host_example
        # upstream saleor  {
        #   server 10.0.3.179:8000; #saleor
        # }

        run_cmd(container, ['apt-get', 'install', 'nginx', '-y'])
        with patch_from_template(
                os.path.join(TEMPLATE_DIR, 'saleor_nginx_template'),
                {'DOMAIN': '.' + domain_lxcws,
                 'USER': user_lxcws}) as patch_settings:
            push_file(container, patch_settings.name,
                      '/etc/nginx/sites-available/saleor')

        # ln -s /etc/nginx/sites-available/saleor /etc/nginx/sites-enabled/
        run_cmd(container, ['ln', '-s', '/etc/nginx/sites-available/saleor',
                            '/etc/nginx/sites-enabled/'])
        run_cmd(container, ['systemctl', 'reload-or-restart', 'nginx'])
        run_cmd(container, ['usermod', '-aG', 'www-data', user_lxcws])

        # using a slightly modified not to say improved
        # uwsgi config then run it
        with patch_from_template(
                os.path.join(TEMPLATE_DIR, 'saleor_uwsgi_template'),
                {'USER': user_lxcws}) as patch_settings:
            push_file(container, patch_settings.name,
                      os.path.join(saleor_dir, 'saleor/wsgi/uwsgi.ini'))

        # lxc-attach -n container_name --clear-env -- sudo -u user_lxcws uwsgi --ini /home/user_lxcws/saleor/saleor/wsgi/uwsgi.ini # noqa
        # note gid=33 so that the socket belongs to toto:www-data
        # lxc-attach -n container_name -- sudo -u user_lxcws SECRET_KEY='**' ALLOWED_HOSTS=domain_lxcws uwsgi /home/user_lxcws/saleor/saleor/wsgi/uwsgi.ini # noqa
        logger.info('Everything installed, running the webshop, don\'t forget '
                    'to set up the nginx reverse proxy on your host')
        run_cmd(container, ['uwsgi', '--ini', 'saleor/wsgi/uwsgi.ini'],
                uid=1000, gid=33, initial_cwd=saleor_dir, env=env)


@click.command()
@click.option('--container_name', '-n')
@click.option('--website_name', '-w')
@click.option('--user_lxcws', '-u')
def install_oscar(container_name, website_name, user_lxcws):
    """Install an Oscar webshop and runs it"""
    container = lxc.Container(container_name)
    if not container.defined:
        logger.debug('Container doesnt exists, create it running lxcws create '
                     '-n container_name')
    else:
        container.start()
        ip = container.get_ips(timeout=30)
        install_common(container_name, user_lxcws)
        run_cmd(container, ['apt-get', 'install', 'python3-virtualenv', '-y'])
        run_cmd(container, ['apt-get', 'install', 'python3-pip', '-y'])
        run_cmd(container,
                ['apt-get', 'install', 'openjdk-8-jre-headless', '-y'])
        run_cmd(container, ['pip3', 'install', 'django-oscar'])
        run_cmd(container, ['pip3', 'install', 'pysolr'])

        # some paths to use later on
        myhome = os.path.join('/home', user_lxcws)

        run_cmd(container, ['rm', '-rf', website_name],
                initial_cwd=myhome)
        run_cmd(container, ['django-admin', 'startproject', website_name],
                uid=1000, gid=1000, initial_cwd=myhome)

        # sed works well for adding a one-liner
        # run_command(container, ['sed', '-i', '/import os/a from oscar.defaults import *', fp]) # noqa

        # that command below works well to 'transfer' a file
        # cat settings_oscar.patch | lxc - attach - n lxcws - - sh - c 'exec cat > /home/toto/templates/settings_oscar.patch' # noqa

        with patch_from_template(os.path.join(TEMPLATE_DIR, 'settings_oscar'
                                                            '.patch'),
                                 {'IP': '"' + ip[0] + '"',
                                  'USER': user_lxcws,
                                  'WEBSITE': website_name}) as patch_settings:
            push_file(container, patch_settings.name,
                      os.path.join(myhome, 'settings_oscar.patch'),
                      uid=1000, gid=1000)

        # lxc-attach -n lxcws -- sudo -u toto sh -c 'patch -p1 -b < /home/toto/settings_oscar.patch' # noqa
        patch_settings_command = 'patch -p3 -b < /home/' + \
                                 user_lxcws + \
                                 '/settings_oscar.patch'
        run_cmd(container, ['sh', '-c', patch_settings_command], uid=1000,
                gid=1000, initial_cwd=myhome)

        with patch_from_template(os.path.join(TEMPLATE_DIR,
                                              'urls_oscar.patch'),
                                 {'USER': user_lxcws, 'WEBSITE': website_name}
                                 ) as patch_urls:
            push_file(container, patch_urls.name,
                      os.path.join(myhome, 'urls_oscar.patch'),
                      uid=1000, gid=1000)
        patch_urls_command = 'patch -p3 -b < '+myhome+'/urls_oscar.patch'
        run_cmd(container, ['sh', '-c', patch_urls_command],
                uid=1000, gid=1000,
                initial_cwd=myhome)

        # solr backend
        run_cmd(container, ['wget', '-nc', 'http://archive.apache.org/dist/lucene/solr/4.7.2/solr-4.7.2.tgz'],  # noqa
                uid=1000, gid=1000, initial_cwd=myhome)
        run_cmd(container, ['tar', 'xzf', 'solr-4.7.2.tgz'],
                uid=1000, gid=1000, initial_cwd=myhome)

        # we run manage.py build_solr_schema and write its output to /home/toto/solr-4.7.2/example/solr/collection1/conf/schema.xml # noqa
        managepybuildsolr = os.path.join(myhome, website_name, 'manage.py')
        # TODO change to tempfile
        with open('/tmp/c1', 'w') as f:
            run_cmd(container,
                    ['python3', managepybuildsolr, 'build_solr_schema'],
                    stdout=f)
        push_file(container, '/tmp/c1',
                  '/home/toto/solr-4.7.2/example/solr/collection1/conf/schema.xml', # noqa
                  uid=1000, gid=1000, initial_cwd='/home/toto')

        # start process in initial_cwd (important, fails if not placed in the
        # correct dir, and not block output HOW
        # => use attach and not attach_wait
        container.attach(lxc.attach_run_command, ['java', '-jar', 'start.jar'],
                         uid=1000, gid=1000,
                         initial_cwd='/home/toto/solr-4.7.2/example')
        run_cmd(container, ['python3', managepybuildsolr, 'migrate'], uid=1000,
                gid=1000, )
        run_cmd(container, ['python3', managepybuildsolr, 'createsuperuser'],
                uid=1000, gid=1000, )
        # ./manage.py rebuild_index --noinput
        # run_command(container, ['python3', managepybuildsolr, 'rebuild_index', '--noinput'], uid=1000, gid=1000,) # noqa

        run_cmd(container, ['pip3', 'install', 'pycountry'])
        run_cmd(container,
                ['python3', managepybuildsolr, 'oscar_populate_countries'],
                uid=1000, gid=1000, )
        container.attach(lxc.attach_run_command,
                         ['python3', managepybuildsolr, 'runserver',
                          '0.0.0.0:8080'], uid=1000, gid=1000)


cli.add_command(create)
cli.add_command(destroy)
cli.add_command(install_oscar)
cli.add_command(install_saleor)
cli.add_command(install_torrent)

if __name__ == '__main__':
    cli()
