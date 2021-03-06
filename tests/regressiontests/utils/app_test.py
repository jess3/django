import os
import unittest
import shutil
import sys
import re

from django import conf, bin, get_version
from django.conf import settings

class AppTestCase(unittest.TestCase):

    DEFAULT_SETTINGS = {
        'INSTALLED_APPS': ['django.contrib.auth', 'django.contrib.contenttypes', 'admin_scripts'],
    }

    def write_settings(self, filename, is_dir=False, **kwargs):
        test_dir = os.path.dirname(os.path.dirname(__file__))
        if is_dir:
            settings_dir = os.path.join(test_dir,filename)
            os.mkdir(settings_dir)
            settings_file = open(os.path.join(settings_dir,'__init__.py'), 'w')
        else:
            settings_file = open(os.path.join(test_dir, filename), 'w')
        settings_file.write('# Settings file automatically generated by regressiontests.admin_scripts test case\n')
        exports = [
            'DATABASES',
            'ROOT_URLCONF'
        ]
        for s in exports:
            if hasattr(settings, s):
                o = getattr(settings, s)
                if not isinstance(o, dict):
                    o = "'%s'" % o
                settings_file.write("%s = %s\n" % (s, o))
                
        settings_dict = dict(self.DEFAULT_SETTINGS)
        
        for k, v in kwargs.items():
            if k == k.upper(): # is a setting
                settings_dict[k] = v
                
        for k, v in settings_dict.items():
            settings_file.write("%s = %s\n" % (k, v))

        settings_file.close()

    def remove_settings(self, filename, is_dir=False):
        test_dir = os.path.dirname(os.path.dirname(__file__))
        full_name = os.path.join(test_dir, filename)
        if is_dir:
            shutil.rmtree(full_name)
        else:
            os.remove(full_name)

        # Also try to remove the compiled file; if it exists, it could
        # mess up later tests that depend upon the .py file not existing
        try:
            if sys.platform.startswith('java'):
                # Jython produces module$py.class files
                os.remove(re.sub(r'\.py$', '$py.class', full_name))
            else:
                # CPython produces module.pyc files
                os.remove(full_name + 'c')
        except OSError:
            pass

    def _ext_backend_paths(self):
        """
        Returns the paths for any external backend packages.
        """
        paths = []
        first_package_re = re.compile(r'(^[^\.]+)\.')
        for backend in settings.DATABASES.values():
            result = first_package_re.findall(backend['ENGINE'])
            if result and result != 'django':
                backend_pkg = __import__(result[0])
                backend_dir = os.path.dirname(backend_pkg.__file__)
                paths.append(os.path.dirname(backend_dir))
        return paths

    def run_test(self, script, args, settings_file=None, apps=None):
        test_dir = os.path.dirname(os.path.dirname(__file__))
        project_dir = os.path.dirname(test_dir)
        base_dir = os.path.dirname(project_dir)
        ext_backend_base_dirs = self._ext_backend_paths()

        # Remember the old environment
        old_django_settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', None)
        if sys.platform.startswith('java'):
            python_path_var_name = 'JYTHONPATH'
        else:
            python_path_var_name = 'PYTHONPATH'

        old_python_path = os.environ.get(python_path_var_name, None)
        old_cwd = os.getcwd()

        # Set the test environment
        if settings_file:
            os.environ['DJANGO_SETTINGS_MODULE'] = settings_file
        elif 'DJANGO_SETTINGS_MODULE' in os.environ:
            del os.environ['DJANGO_SETTINGS_MODULE']
        python_path = [test_dir, base_dir]
        python_path.extend(ext_backend_base_dirs)
        os.environ[python_path_var_name] = os.pathsep.join(python_path)

        # Build the command line
        executable = sys.executable
        arg_string = ' '.join(['%s' % arg for arg in args])
        if ' ' in executable:
            cmd = '""%s" "%s" %s"' % (executable, script, arg_string)
        else:
            cmd = '%s "%s" %s' % (executable, script, arg_string)

        # Move to the test directory and run
        os.chdir(test_dir)
        try:
            from subprocess import Popen, PIPE
            p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdin, stdout, stderr = (p.stdin, p.stdout, p.stderr)
        except ImportError:
            stdin, stdout, stderr = os.popen3(cmd)
        out, err = stdout.read(), stderr.read()

        # Restore the old environment
        if old_django_settings_module:
            os.environ['DJANGO_SETTINGS_MODULE'] = old_django_settings_module
        if old_python_path:
            os.environ[python_path_var_name] = old_python_path
        # Move back to the old working directory
        os.chdir(old_cwd)

        return out, err

    def run_django_admin(self, args, settings_file=None):
        bin_dir = os.path.abspath(os.path.dirname(bin.__file__))
        return self.run_test(os.path.join(bin_dir,'django-admin.py'), args, settings_file)

    def run_manage(self, args, settings_file=None):
        conf_dir = os.path.dirname(conf.__file__)
        template_manage_py = os.path.join(conf_dir, 'project_template', 'manage.py')

        test_dir = os.path.dirname(os.path.dirname(__file__))
        test_manage_py = os.path.join(test_dir, 'manage.py')
        shutil.copyfile(template_manage_py, test_manage_py)

        stdout, stderr = self.run_test('./manage.py', args, settings_file)

        # Cleanup - remove the generated manage.py script
        os.remove(test_manage_py)

        return stdout, stderr

    def assertNoOutput(self, stream):
        "Utility assertion: assert that the given stream is empty"
        self.assertEquals(len(stream), 0, "Stream should be empty: actually contains '%s'" % stream)
    def assertOutput(self, stream, msg):
        "Utility assertion: assert that the given message exists in the output"
        self.failUnless(msg in stream, "'%s' does not match actual output text '%s'" % (msg, stream))