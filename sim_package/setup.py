from setuptools import setup, find_packages
from setuptools.command.install import install
from Cython.Build import cythonize
import subprocess as sp
import os

PACKAGE_NAME = 'TrafficSimPATH'

class CustomSPTInstall(install):

    def run(self):
        # think about moving to setup script...
        repo_name = 'sp'
        repo = f'https://github.com/cb-cities/{repo_name}.git'
        print('cloning shortest paths repo...')
        sp.run(f'rm -rf sp && git clone -b dataframe {repo}', shell=True, cwd='src/sim_package')

        print('init cmake...')
        sp.run(f'cmake -DCMAKE_BUILD_TYPE=Release ./CMakeLists.txt', shell=True, cwd=f'src/sim_package/{repo_name}')

        print('compiling shortest paths library...')
        sp.run(f'make clean && make -j{max(os.cpu_count() // 2, 1)}', shell=True, cwd=f'src/sim_package/{repo_name}')

        print('clean up...')
        sp.run(f'rm -rf ../dlls && mkdir ../dlls && mv liblsp.* ../dlls && cd .. && rm -rf {repo_name}', shell=True, cwd=f'src/sim_package/{repo_name}')
        # sp.run('tree')
        super().run()


setup(
    name=PACKAGE_NAME,
    version='0.0.4',    
    description='A traffic simulation package made by berkeley PATH',
    url='https://github.com/ucbtrans/Fall2021/traffic_sim',
    author='Abhinav Dhulipala',
    author_email='abhinav.dhulipala@berkeley.edu',
    license='MIT',
    install_requires=['numpy',
                      'shapely',
                      'pandas',
                      'cython'
                      ],
    package_dir={"": "src"},
    #packages=find_packages(where='src'),
    package_data={'sim_package': ['sim_package/dlls/liblsp.*']},
    include_package_data=True,
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',  
        'Operating System :: POSIX :: Linux', 
        'Programming Language :: Python :: 3.9',
    ],
    cmdclass={'install': CustomSPTInstall},
    #ext_modules=cythonize("src/sim_package/queue_model.pyx", language_level='3')
)
