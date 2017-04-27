import logging
import uuid
import pytest
import lxc

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.DEBUG)


@pytest.fixture(scope='module')
def temp_container(request):
    container_name = getattr(request.module, "cccc", str(uuid.uuid1()))
    logger.debug('begin {}'.format(container_name))
    c = lxc.Container(container_name)
    if c.defined:
        logger.info('Container already exists')
    else:
        # Create the container rootfs
        if not c.create(
                'download', lxc.LXC_CREATE_QUIET,
                {'dist': 'ubuntu', 'release': 'xenial', 'arch': 'amd64'}
        ):
            logger.debug('Failed to create the container rootfs')
        else:
            logger.info('Created the container rootfs')
            # Save the configuration
            c.save_config()
    if not c.running:
        c.start()
    yield c
    if c.running:
        c.stop()
    c.destroy()
    logger.debug('end {}'.format(container_name))


d = {'debian': (['jessie', 'stretch', 'sid'], ['amd64']),
     'ubuntu': (['xenial', 'yakkety', 'zesty'], ['amd64', 'i386'])}

dist_permut = [(dist, release, arch) for dist, v in d.items() for release in v[0] for arch in v[1]]

@pytest.fixture(scope='module', params=dist_permut, ids=['{}-{}-{}'.format(d, r, a) for d,r,a in dist_permut])
def dist(request):
    yield request.param


@pytest.fixture(scope='module')
def meta_container(dist):
    print(dist)
    container_name = str(uuid.uuid1())
    logger.debug('begin {}'.format(container_name))
    c = lxc.Container(container_name)
    if c.defined:
        logger.info('Container already exists')
    else:
        # Create the container rootfs

        logger.debug(
            'Create the container with dist: {} '.format(dist))
        if not c.create(
                'download', lxc.LXC_CREATE_QUIET,
                {'dist': dist[0], 'release': dist[1],
                 'arch': dist[2]}
        ):
            logger.debug('Failed to create the container rootfs')
        else:
            logger.info('Created the container rootfs')
            # Save the configuration
            c.save_config()
    if not c.running:
        c.start()
    yield c
    if c.running:
        c.stop()
    c.destroy()
