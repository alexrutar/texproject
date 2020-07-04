from setuptools import setup, find_packages
from texproject import __version__, __repo__
def readme():
    with open('README.rst','r') as f:
        return f.read()

setup(
    name='texproject',
    version=__version__,
    description='An automatic LaTeX project manager.',
    long_description=readme(),
    url=__repo__,
    author='Alex Rutar',
    author_email='public@rutar.org',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3.8',
        'License :: OSI Approved :: MIT License'
        ],
    keywords='LaTeX template project',
    license='MIT',
    python_requires='>=3.7',
    packages=find_packages(),
    install_requires=[
        'pyYAML>=3.13',
        'Jinja2>=2.11.2',
        'xdg>=4.0.1',
        'click>=7.1'
        ],
    include_package_data=True,
    entry_points={'console_scripts': ['tpr = texproject.command:cli']},
    zip_safe=False
    )

