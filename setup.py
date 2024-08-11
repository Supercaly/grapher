from setuptools import find_packages, setup

setup(name='grapher',
      version='1.2',
      description='Program that auto creates graphs form InfluxDB data',
      author='Lorenzo Calisti',
      author_email='l.calisti@campus.uniurb.it',
      packages=find_packages(),
      entry_points={
          'console_scripts': ['grapher=grapher.cli:main']
      },
      license='MIT',
      install_requires=[
          'matplotlib',
          'numpy',
          'pandas',
          'colorlog'
      ]
     )
