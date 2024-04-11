'''
import game
from mioconn import mio_connect
import sys
import subprocess

subprocess.call(mio_connect.main(sys.argv[1:]))
subprocess.call(['python','game.py'])
'''
'''
import os
command ='python ./mioconn/mio_connect.py -and python game.py'
os.system(command)



import runpy
runpy.run_path(path_name='mioconn/mio_connect.py')
runpy.run_path(path_name='game.py')
'''

import game
import sys
from mioconn import mio_connect
not_connected = 1
while not_connected:
    mio_connect.main(sys.argv[1:])
    not_connected = 0
if not not_connected:
    game.main()