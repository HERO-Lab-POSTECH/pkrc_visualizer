from setuptools import find_packages, setup

package_name = 'pkrc_visualizer'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # launch 파일은 Task 4 Step 5에서 작성하면서 이 줄을 추가:
        # ('share/' + package_name + '/launch', ['launch/pkrc_visualizer.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='luckkim123',
    maintainer_email='luckkim123@gmail.com',
    description='PKRC integrated PyQt5 visualizer.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'pkrc_viz = pkrc_visualizer.app:main',
        ],
    },
)
