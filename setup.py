from setuptools import setup, find_packages

setup(
    name         = 'BeanstalkPlugin',
    version      = '0.1',
    packages     = find_packages(),
    entry_points = {
        'trac.plugins': [
            'BeanstalkPlugin = BeanstalkPlugin.BeanstalkPlugin',
        ],
    }
)
