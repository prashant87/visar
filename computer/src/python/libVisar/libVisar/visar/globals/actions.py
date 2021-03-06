from ...OpenGL.utils import Logger

class Actions(object):
    '''Class to store list of funcitons avaliable for buttons/voice'''
    
    @classmethod
    def get_actions(self, State):
        '''function generates the dictionary for input state'''
        return {
            #'example'       : lambda: Logger.warn("Example button pressed!"),
            #'example'       : lambda: Logger.warn("Current battery level:" + str(State.battery)),
            'make call'     : State.make_call,
            'end call'      : State.end_call,
            'toggle map'    : State.hide_map,
            'start voice'   : State.toggle_vc,
            'stop voice'    : State.toggle_vc,
            #'list peers'    : lambda: Logger.warn("Peers: %s" % (State.network_peers,)),
            #'set target'    : State.set_target,
            #'update status' : State.update_status,
        }
