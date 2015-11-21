import os
import shlex
import subprocess
import sys

from vr.common.utils import randchars


# Ideally, the value of DJANGO_SETTINGS_MODULE would be "vr.server.settings".
# Unfortunately, that value doesn't work with the standard ``manage.py`` file
# provided by Django 1.4+, due to ``vr`` being a namespaced Python package.
# Therefore, the following ``sys.path`` trick allows us to use
# "server.settings" as the value of the Django settings module.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
)


here = os.path.dirname(os.path.abspath(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'server.settings'
os.environ['APP_SETTINGS_YAML'] = os.path.join(here, 'testconfig.yaml')


from django.contrib.auth.models import User


def sh(cmd):
    subprocess.call(shlex.split(cmd), stderr=subprocess.STDOUT)


def dbsetup():
    here = os.path.dirname(os.path.abspath(__file__))
    project = os.path.dirname(here)
    os.chdir(here)
    sql = os.path.join(here, 'dbsetup.sql')
    sh('psql -f %s -U postgres' % sql)

    # Now create tables
    manage = os.path.join(project, 'manage.py')
    sh('python %s syncdb --noinput' % manage)
    sh('python %s migrate' % manage)


def randurl():
    return 'http://%s/%s' % (randchars(), randchars())


def get_user():
    u = User(username=randchars())
    u.set_password('password123')
    u.is_admin = True
    u.is_staff = True
    u.save()
    return u