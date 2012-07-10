from setuptools import setup, find_packages


setup(
    name='jinja2js',
    version='0.9.0',
    description='Compiles Jinja2 templates to JS.',
    long_description=open('README.rst').read(),
    author='Matt Basta',
    author_email='me@mattbasta.com',
    url='http://github.com/mattbasta/jinja2js',
    license='BSD',
    packages=find_packages(exclude=['tests', 'tests/*',]),
    include_package_data=True,
    zip_safe=False,
    install_requires=[p.strip() for p in
                      open('./requirements.txt') if
                      not p.startswith(('#', '-e'))],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
