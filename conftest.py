import logging
import uuid
import pytest
import lxc

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.DEBUG)


@pytest.fixture(scope='session')
def temp_container(request):
    container_name = getattr(
        request.session, "container_name", str(uuid.uuid1()))
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
