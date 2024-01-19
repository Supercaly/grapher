from setuptools import setup

setup(name='Grapher',
      version='1.0',
      description='Program to auto create graphs form InfluxDB data',
      author='Lorenzo Calisti',
      author_email='l.calisti@campus.uniurb.it',
      scripts=['grapher.py'],
      license='MIT',
      install_requires=[
          'python-dateutil',
          'matplotlib',
          'numpy',
          'pandas'
      ]
     )