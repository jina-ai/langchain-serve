import platform
import sys
from os import path

import pkg_resources
from setuptools import find_packages, setup


def get_requirements_list(f):
    with pathlib.Path(f).open() as requirements_txt:
        requirements_list = [
            str(requirement)
            for requirement in pkg_resources.parse_requirements(requirements_txt)
        ]
        return requirements_list


if sys.version_info < (3, 7, 0):
    raise OSError(f'langchain-serve requires Python >=3.7, but yours is {sys.version}')

try:
    pkg_name = 'langchain-serve'
    libinfo_py = path.join('lcserve', '__init__.py')
    libinfo_content = open(libinfo_py, 'r', encoding='utf8').readlines()
    version_line = [l.strip() for l in libinfo_content if l.startswith('__version__')][
        0
    ]
    exec(version_line)  # gives __version__
except FileNotFoundError:
    __version__ = '0.0.0'

try:
    with open('README.md', encoding='utf8') as fp:
        _long_description = fp.read()
except FileNotFoundError:
    _long_description = ''

import os
import pathlib

install_requires = get_requirements_list(
    os.path.join(os.path.dirname(__file__), 'requirements.txt')
)
sys_platform = platform.system().lower()


setup(
    name=pkg_name,
    packages=find_packages(),
    version=__version__,
    include_package_data=True,
    description='Langchain Serve - serve your langchain apps on Jina AI Cloud.',
    author='Jina AI',
    author_email='hello@jina.ai',
    license='Apache 2.0',
    url='https://github.com/jina-ai/langchain-serve/',
    download_url='https://github.com/jina-ai/langchain-serve/tags',
    long_description=_long_description,
    long_description_content_type='text/markdown',
    zip_safe=False,
    setup_requires=['setuptools>=18.0', 'wheel'],
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'langchain-serve=lcserve.__main__:serve',
            'lc-serve=lcserve.__main__:serve',
            'lcserve=lcserve.__main__:serve',
        ],
    },
    extras_require={
        'test': [
            'pytest',
            'pytest-asyncio',
            'psutil',
        ],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Environment :: Console',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
    ],
    project_urls={
        'Documentation': 'https://docs.jina.ai',
        'Source': 'https://github.com/jina-ai/now',
        'Tracker': 'https://github.com/jina-ai/now/issues',
    },
    keywords='jina langchain llm neural-network deep-learning data democratization',
)
