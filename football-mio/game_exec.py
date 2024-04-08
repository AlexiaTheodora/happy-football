
import game
from mioconn import mio_connect
import sys

game.main()
mio_connect.main(sys.argv[1:])