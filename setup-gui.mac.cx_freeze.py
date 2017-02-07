from cx_Freeze import setup, Executable

import sys
import os
import shutil
import version
import site

base_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
sys.argv.append('bdist_mac')
sys.argv.append('--qt-menu-nib=/opt/local/libexec/qt5/plugins/')

try:
    shutil.rmtree(os.path.join(base_dir, 'build'))
except:
    pass

try:
    shutil.rmtree(os.path.join(base_dir, 'dist'))
except:
    pass

includes = [
    'lxml._elementpath',
    'modules.default_css',
    'PyQt5.QtCore', 
    'PyQt5.QtGui',
    'PyQt5.QtWidgets'
]

excludes = [
    'pywin',
    'Tkconstants',
    'Tkinter',
    'tcl'
]

data_files = [
    (os.path.join(base_dir, 'modules', 'dictionaries'), 'dictionaries'),
    (os.path.join(base_dir, 'profiles'), 'profiles'),
    (os.path.join(base_dir, 'fb2mobi.config'), 'fb2mobi.config'),
    (os.path.join(base_dir, 'spaces.xsl'), 'spaces.xsl'),
    (os.path.join(base_dir, 'kindlegen'), 'kindlegen')
]


plist = {}

# plist = { 
#     'CFBundleDocumentTypes': [{
#     'CFBundleTypeName': 'Folder',
#     'CFBundleTypeRole': 'Viewer',
#     'LSItemContentTypes': ['public.folder'],
#     'CFBundleTypeExtensions': ['fb2', 'zip'],
#     'CFBundleTypeName': 'FB2 Document',
#     'CFBundleTypeRole': 'Viewer',
#   }]
# }


setup(
    name = "fb2mobi-gui",
    version = version.VERSION,
    options={
        'build_exe': {
#            'silent': 1,
            #'build_exe': 'dist',
            'zip_exclude_packages': '',
            'zip_include_packages': '*',
            'include_files': data_files,
            'includes': includes,
            'excludes': excludes,
        },
        'bdist_mac': {
            'iconfile': 'ui/fb2mobi.icns',
            'custom_info_plist': plist,
            'qt_menu_nib': '/opt/local/libexec/qt5/plugins/'
        }
    },
    executables = [
        Executable('fb2mobi-gui.py')
    ]
)
