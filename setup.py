from setuptools import setup

setup(
    name="verminator",
    version='1.0.0',
    url='http://172.16.1.41:10080/TDC/verminator',
    author='Xiaming Chen',
    author_email='xiaming.chen@transwarp.io',
    description='TDC image Version management tERMINATOR.',
    packages=['verminator'],
    keywords=['utility', 'versioning'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Python Modules',
   ],
)