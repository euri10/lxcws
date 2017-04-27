import re
import logging

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.DEBUG)


def test_all_dist(dist):
    print(dist)


def test_keys(meta_container):
    with open(meta_container.config_file_name) as conf_file:
        lines = conf_file.readlines()
    f_config = []
    for potential_option in lines:
        m = re.match('^([^#]+) = (.*)$', potential_option)
        if m is not None:
            f_key = m.group(1)
            f_value = m.group(2)
            f_config.append((f_key, f_value))
    for k in meta_container.get_keys():
        try:
            k_accessible = meta_container.get_config_item(k)
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
