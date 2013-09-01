from setuptools import setup, find_packages
from os.path import join, dirname
from omnibust import __version__


def read(fname):
    with open(join(dirname(__file__), fname), 'r') as f:
        return f.read()


setup(
    name='omnibust',
    version=__version__,
    description='Cachebusting Script that works everywhere',
    long_description=(
        read('README.md') + "\n" +
        read('LICENSE')
    ),
    author='Manuel Barkhau',
    author_email='mbarkhau@gmail.com',
    url='http://bitbucket.org/mbarkhau/omnibust/',
    license="BSD License",
    packages=find_packages(),
    entry_points={'console_scripts': ['omnibust = omnibust:main']},
    keywords="cachebust web",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        'Topic :: Utilities',
    ],

)
