from setuptools import setup, find_packages

setup(
    name         = 'BeanstalkPlugin',
    version      = '0.3',
    packages     = find_packages(),
    entry_points = {
        'trac.plugins': [
            'BeanstalkPlugin = BeanstalkPlugin.BeanstalkPlugin',
        ],
    }
)
