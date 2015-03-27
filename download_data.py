import os
import tempfile
import urllib2
import urlparse
import tarfile
import contextlib
import shutil
import re

VOC_VAL_URL = 'http://pascallin.ecs.soton.ac.uk/challenges/VOC/voc2007/VOCtrainval_06-Nov-2007.tar'
VOC_TEST_URL = 'http://pascallin.ecs.soton.ac.uk/challenges/VOC/voc2007/VOCtest_06-Nov-2007.tar'

CNN_MEAN = 'http://www.robots.ox.ac.uk/~vgg/software/deep_eval/releases/bvlc/VGG_mean.binaryproto'
CNN_PROTO = 'http://www.robots.ox.ac.uk/~vgg/software/deep_eval/releases/bvlc/VGG_CNN_M_128_deploy.prototxt'
CNN_MODEL = 'http://www.robots.ox.ac.uk/~vgg/software/deep_eval/releases/bvlc/VGG_CNN_M_128.caffemodel'

NEG_IMAGES = 'http://www.robots.ox.ac.uk/~vgg/software/deep_eval/releases/neg_images.tar'

@contextlib.contextmanager
def make_temp_directory():

    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


def download_url(url, fname):

    data = urllib2.urlopen(url)
    with open(fname, 'wb') as fp:
        fp.write(data.read())

    return fname


def prepare_config_proto(base_path, dset_dir=None):

    orig_file = os.path.join(base_path, 'config.prototxt')
    tmp_file = os.path.join(base_path, 'config.prototxt.new')

    dset_dir_regex = None
    if dset_dir:
        if os.path.isabs(dset_dir):
            dset_dir_regex = '<DSET_DIR>'
        else:
            dset_dir_regex = '".*<DSET_DIR>.*"'

    with open(orig_file, 'r') as fp_r:
        with open(tmp_file, 'w') as fp_w:
            for line in fp_r:
                fp_w.write(line.replace('<BASE_DIR>', base_path))
                if dset_dir_regex:
                    line = re.sub(dset_dir_regex, '"%s"' % base_path, line)

    os.remove(orig_file)
    shutil.move(tmp_file, orig_file)


def find_config_field_(config_str, field):

    # split field into subparts if required
    fields = field.split('.')

    # find leaf field
    match = {}

    match['start_idx'] = re.search(fields[-1] + ':[ ]*', config_str).end(0)
    if not match['start_idx']:
        raise RuntimeError('Could not locate field %s in config file' % field)

    newline_regex = re.compile('[ ]*\n')
    match['end_idx'] = newline_regex.search(config_str, match['start_idx']).start(0)
    if not match['end_idx']:
        raise RuntimeError('Could not locate field %s in config file' % field)

    match['value'] = config_str[match['start_idx']:match['end_idx']]

    # check leaf field is child of parent fields
    search_pos = match['start_idx']
    for parent_field in reversed(fields[:-1]):
        idx = config_str.rfind('{', 0, search_pos)
        if idx == -1:
            raise RuntimeError('Could not locate field %s in config file' % field)
        search_pos = idx

        parent_field_start_idx = re.search(parent_field + ':[ ]*$', config_str[:search_pos])
        if not parent_field_start_idx:
            raise RuntimeError('Could not locate field %s in config file' % field)

        search_pos = parent_field_start_idx

    return match


def set_config_field(base_path, field, new_value):

    orig_file = os.path.join(base_path, 'config.prototxt')
    tmp_file = os.path.join(base_path, 'config.prototxt.new')

    with open(orig_file, 'r') as fp_r:
        old_config_str = fp_r.read()

    # super-simple and naive replacing of field values by searching for text of form:
    # <FIELD_NAME>: <VALUE>\n
    field_match = find_config_field_(old_config_str, field)

    new_value = str(new_value)
    if leaf_field_match['value'][0] == '"':
        new_value = '"%s"' % new_value

    # set field contents
    new_config_str = (old_config_str[:leaf_field_match['start_idx']]
                      + new_value
                      + old_config_str[leaf_field_match['end_idx']:])

    with open(tmp_file, 'w') as fp_w:
        fp_w.write(new_config_str)

    os.remove(orig_file)
    shutil.move(tmp_file, orig_file)


def get_config_field(base_path, field):

    config_file = os.path.join(base_path, 'config.prototxt')

    with open(config_file, 'r') as fp_r:
        config_str = fp_r.read()

    field_match = find_config_field_(config_str, field)

    return field_match['value']


def download_voc_data(target_path):

    if not os.path.exists(target_path):
        os.makedirs(target_path)

    with make_temp_directory() as temp_dir:

        urls = {'val': VOC_VAL_URL, 'test': VOC_TEST_URL}
        fnames = {}
        for set, url in urls.iteritems():
            print 'Downloading %s: %s...' % (set, url)
            fnames[set] = download_url(url, os.path.join(temp_dir, set + '.tar'))

        for set, fname in fnames.iteritems():
            print 'Extracting %s: %s...' % (set, fname)
            with tarfile.open(fname) as tar:
                tar.extractall(target_path)


def download_neg_images(target_path):

    if not os.path.exists(target_path):
        os.makedirs(target_path)

    with make_temp_directory() as temp_dir:

        print 'Downloading %s...' % NEG_IMAGES
        fname = download_url(NEG_IMAGES, os.path.join(temp_dir, NEG_IMAGES.split('/')[-1].split('#')[0].split('?')[0]))

        print 'Extracting %s...' % fname
        with tarfile.open(fname) as tar:
            tar.extractall(target_path)


def download_models(target_path):

    if not os.path.exists(target_path):
        os.makedirs(target_path)

    with make_temp_directory() as temp_dir:

        urls = [CNN_MEAN, CNN_PROTO, CNN_MODEL]
        fnames = []
        for url in urls:
            print 'Downloading %s...' % url
            fnames.append(download_url(url, os.path.join(temp_dir, url.split('/')[-1].split('#')[0].split('?')[0])))

        for fname in fnames:
            print 'Copying %s...' % fname
            shutil.copyfile(fname, os.path.join(target_path, os.path.split(fname)[1]))


if __name__ == "__main__":

    file_dir = os.path.dirname(os.path.realpath(__file__))
    prepare_config_proto(file_dir, 'VOCdevkit/VOC2007')

    target_dir = os.path.join(file_dir, 'server_data', 'dset_images')
    download_voc_data(target_dir)

    target_dir = os.path.join(file_dir, 'server_data', 'neg_images')
    download_neg_images(target_dir)

    target_dir = os.path.join(file_dir, 'model_data')
    download_models(target_dir)
