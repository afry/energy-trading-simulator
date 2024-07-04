from setuptools import find_packages, setup

with open('README.md', 'r') as f:
    readme = f.read()

setup(name='tradingplatformpoc',
      version='3.13.2.dev',
      description='A trading platform which enables physical entities to buy and sell energy using bids and agents.',
      long_description=readme,
      url='https://gitlab01.afdrift.se/futuretechnologies/tornet-jonstaka/trading-platform-poc',
      author='AFRY',
      author_email='',
      license='Unlicensed',
      packages=find_packages(),
      test_suite='tests',
      python_requires='>=3.9',
      include_package_data=True,
      data_files=['requirements.txt'],
      package_data={'': ["data/*"]},
      zip_safe=False
      )
