#distutils: language=c++

import time
import random
from . import interface
from shapely.wkt import loads
import numpy as np

from libcpp.map cimport map as cpp_map
from libcpp.vector cimport vector as cpp_vector


cdef class Node:
    def __init__(self, node_id, lon, lat, ntype, osmid=None):
        self.nid = node_id
        self.lon = lon
        self.lat = lat
        self.ntype = ntype
        self.osmid = osmid
        ### derived
        self.in_links = {} ### {in_link_id: straight_ahead_out_link_id, ...}
        self.out_links = []
        self.go_vehs = [] ### veh that moves in this time step
        self.status = ''

    def create_virtual_node(self):
        return Node('vn_source_{}'.format(self.nid), self.lon+0.001, self.lat+0.001, 'vn_source')

    def create_virtual_link(self):
        return Link('vl_in_{}'.format(self.nid), 100, 0, 0, 100000, 'vl_in', 'vn_source_{}'.format(self.nid), self.nid, 'LINESTRING({} {}, {} {})'.format(self.lon+0.001, self.lat+0.001, self.lon, self.lat), simulation=self.simulation)

    def calculate_straight_ahead_links(self, node_id_dict=None, link_id_dict=None):
        cdef double x_start, y_start, x_end, y_end
        for il in self.in_links.keys():
            x_start = node_id_dict[link_id_dict[il].start_nid].lon
            y_start = node_id_dict[link_id_dict[il].start_nid].lat
            in_vec = (self.lon-x_start, self.lat-y_start)
            sa_ol = None ### straight ahead out link
            ol_dir = 180
            for ol in self.out_links:
                x_end = node_id_dict[link_id_dict[ol].end_nid].lon
                y_end = node_id_dict[link_id_dict[ol].end_nid].lat
                out_vec = (x_end-self.lon, y_end-self.lat)
                dot = (in_vec[0]*out_vec[0] + in_vec[1]*out_vec[1])
                det = (in_vec[0]*out_vec[1] - in_vec[1]*out_vec[0])
                new_ol_dir = np.arctan2(det, dot)*180/np.pi
                if abs(new_ol_dir)<ol_dir:
                    sa_ol = ol
                    ol_dir = new_ol_dir
            if (abs(ol_dir)<=45) and link_id_dict[il].ltype[0:2]!='vl':
                self.in_links[il] = sa_ol

    def find_go_vehs(self, go_link):
        go_vehs_list = []
        incoming_lanes = int(np.floor(go_link.lanes))
        incoming_vehs = len(go_link.queue_veh)
        for ln in range(min(incoming_lanes, incoming_vehs)):
            agent_id = go_link.queue_veh[ln]
            try:
                agent_next_node, ol, agent_dir = self.agent_id_dict[agent_id].prepare_agent(self.nid, node2link_dict=self.node2link_dict, node_id_dict=self.node_id_dict)
            except AssertionError:
                pass
            go_vehs_list.append([agent_id, agent_next_node, go_link.lid, ol, agent_dir])
        return go_vehs_list

    # must find non-conflicts before running model at each time step. decoupled due to write=read data deps
    def non_conflict_vehs(self, t_now, link_id_dict=None, agent_id_dict=None, node2link_dict=None, node_id_dict=None):

        self.go_vehs = []
        self.link_id_dict = link_id_dict
        self.agent_id_dict = agent_id_dict
        self.node2link_dict = node2link_dict
        self.node_id_dict = node_id_dict
        ### a primary direction
        in_links = [l for l in self.in_links.keys() if len(link_id_dict[l].queue_veh)>0]

        if len(in_links) == 0:
            return self.go_vehs
        go_link = link_id_dict[random.choice(in_links)]
        go_vehs_list = self.find_go_vehs(go_link)
        self.go_vehs += go_vehs_list

        ### a non-conflicting direction
        if (np.min([veh[-1] for veh in go_vehs_list]) < -45) or (go_link.ltype=='vl_in'):
            ### no opposite veh allows to move if there is left turn veh in the primary direction; or if the primary incoming link is a virtual link
            return self.go_vehs 
        if self.in_links[go_link.lid] is None:
            return self.go_vehs ### no straight ahead opposite links
        op_go_link = link_id_dict[self.in_links[go_link.lid]]
        link_id = node2link_dict[(op_go_link.end_nid, op_go_link.start_nid)]
        if link_id not in link_id_dict:
          # straight ahead link is one way
          return self.go_vehs
        op_go_link = link_id_dict[link_id]
        op_go_vehs_list = self.find_go_vehs(op_go_link)
        
        self.go_vehs += [veh for veh in op_go_vehs_list if veh[-1] > -45]


    def run_node_model(self, t_now):
        ### Agent reaching destination
        for [agent_id, next_node, il, ol, _] in self.go_vehs:
            veh_len = self.agent_id_dict[agent_id].veh_len

            ### arrival
            if (next_node is None) and (self.nid == self.agent_id_dict[agent_id].destin_nid):
                self.link_id_dict[il].send_veh(t_now, agent_id, self.agent_id_dict)
                self.agent_id_dict[agent_id].move_agent(t_now, self.nid, None, 'arr')

            ### no storage capacity downstream
            elif self.link_id_dict[ol].st_c < veh_len:
                pass ### no blocking, as # veh = # lanes
            ### inlink-sending, outlink-receiving both permits
            elif self.link_id_dict[il].ou_c >= 1 and self.link_id_dict[ol].in_c >= 1:
                ### before move agent as it uses the old agent.cl_enter_time
                self.link_id_dict[il].send_veh(t_now, agent_id, self.agent_id_dict)
                self.agent_id_dict[agent_id].move_agent(t_now, self.nid, next_node, 'flow')
                self.link_id_dict[ol].receive_veh(agent_id)
            ### either inlink-sending or outlink-receiving or both exhaust
            else:

                control_cap = min(self.link_id_dict[il].ou_c, self.link_id_dict[ol].in_c)
                toss_coin = random.choices([0,1], weights=[1-control_cap, control_cap], k=1)
                if toss_coin[0]: ### vehicle can move
                    ### before move agent as it uses the old agent.cl_enter_time
                    self.link_id_dict[il].send_veh(t_now, agent_id, self.agent_id_dict)
                    self.agent_id_dict[agent_id].move_agent(t_now, self.nid, next_node, 'chance')
                    self.link_id_dict[ol].receive_veh(agent_id)
                else: ### even though vehicle cannot move, the remaining capacity needs to be adjusted
                    if self.link_id_dict[il].ou_c < self.link_id_dict[ol].in_c:
                       self.link_id_dict[il].ou_c = max(0, self.link_id_dict[il].ou_c - 1)
                    elif self.link_id_dict[ol].in_c < self.link_id_dict[il].ou_c:
                        self.link_id_dict[ol].in_c = max(0, self.link_id_dict[ol].in_c - 1)
                    else:
                        self.link_id_dict[il].ou_c -= 1
                        self.link_id_dict[ol].in_c -= 1


cdef class Link:

    def __init__(self, link_id, lanes, length, fft, capacity, ltype, start_nid, end_nid, geometry, g):
        ### input
        self.lid = link_id
        self.lanes = lanes
        self.length = length
        self.fft = fft
        self.capacity = capacity
        self.ltype = ltype
        self.start_nid = start_nid
        self.end_nid = end_nid
        self.geometry = loads(geometry)
        self.g = g
        ### derived
        self.store_cap = max(18, length*lanes) ### at least allow any vehicle to pass. i.e., the road won't block any vehicle because of the road length
        self.in_c = self.capacity / 3600.0 # capacity in veh/s
        self.ou_c = self.capacity / 3600.0
        self.st_c = self.store_cap # remaining storage capacity
        self.midpoint = list(self.geometry.interpolate(0.5, normalized=True).coords)[0]
        ### empty
        self.queue_veh = [] # [(agent, t_enter), (agent, t_enter), ...]
        self.run_veh = []
        self.travel_time_list = [] ### [(t_enter, dur), ...] travel time of each agent left the link in a given period; reset at times
        self.travel_time = fft
        self.start_node = None
        self.end_node = None

    def send_veh(self, t_now, agent_id, agent_id_dict=None):
        ### remove the agent from queue
        self.queue_veh = [v for v in self.queue_veh if v!=agent_id]
        self.ou_c = max(0, self.ou_c-1)
        if self.ltype[0:2] != 'vl': 
            self.travel_time_list.append((t_now, t_now - agent_id_dict[agent_id].cl_enter_time))

    def receive_veh(self, agent_id):
        self.run_veh.append(agent_id)
        self.in_c = max(0, self.in_c-1)

    def run_link_model(self, t_now):
        if t_now%60 == 0: 
            self.update_travel_time(t_now, link_time_lookback_freq=60)
        for agent_id in self.run_veh:
            if self.simulation.all_agents[agent_id].cl_enter_time < t_now - self.fft:
                self.queue_veh.append(agent_id)
        self.run_veh = [v for v in self.run_veh if v not in self.queue_veh]
        ### remaining spaces on link for the node model to move vehicles to this link
        self.st_c = self.store_cap - np.sum([self.simulation.all_agents[agent_id].veh_len for agent_id in self.run_veh + self.queue_veh])
        self.in_c, self.ou_c = self.capacity/3600, self.capacity/3600

    def update_travel_time(self, t_now, link_time_lookback_freq=None):
        self.travel_time_list = [(t_rec, dur) for (t_rec, dur) in self.travel_time_list if (t_now-t_rec < link_time_lookback_freq)]
        if len(self.travel_time_list) > 0:
            self.travel_time = np.mean([dur for (_, dur) in self.travel_time_list])
            self.g.update_edge(self.start_nid, self.end_nid, <double> self.travel_time)

class Agent:
    def __init__(self, id, origin_nid, destin_nid, dept_time, veh_len, gps_reroute, simulation=None):
        #input
        self.aid = id
        self.origin_nid = origin_nid
        self.destin_nid = destin_nid
        self.dept_time = dept_time
        self.veh_len = veh_len
        self.gps_reroute = gps_reroute
        self.simulation = simulation
        ### derived
        self.cls = 'vn_source_{}'.format(self.origin_nid) # current link start node
        self.cle = self.origin_nid # current link end node
        ### Empty
        self.route_igraph = []
        self.find_route = None
        self.status = None
        self.cl_enter_time = None

    def load_trips(self, t_now):
        if (self.dept_time == t_now):
            initial_edge = self.simulation.node2link_dict[self.route_igraph[0]]
            self.simulation.all_links[initial_edge].run_veh.append(self.aid)
            self.status = 'loaded'
            self.cl_enter_time = t_now

    def prepare_agent(self, node_id, node2link_dict=None, node_id_dict=None):
        assert self.cle == node_id, "agent next node {} is not the transferring node {}, route {}".format(self.cle, node_id, self.route_igraph)
        if self.destin_nid == node_id: ### current node is agent destination
            return None, None, 0 ### id, next_node, dir
        agent_next_node = [end for (start, end) in self.route_igraph if start == node_id][0]
        ol = node2link_dict[(node_id, agent_next_node)]
        x_start, y_start = node_id_dict[self.cls].lon, node_id_dict[self.cls].lat
        x_mid, y_mid = node_id_dict[node_id].lon, node_id_dict[node_id].lat
        x_end, y_end = node_id_dict[agent_next_node].lon, node_id_dict[agent_next_node].lat
        in_vec, out_vec = (x_mid-x_start, y_mid-y_start), (x_end-x_mid, y_end-y_mid)
        dot, det = (in_vec[0]*out_vec[0] + in_vec[1]*out_vec[1]), (in_vec[0]*out_vec[1] - in_vec[1]*out_vec[0])
        agent_dir = np.arctan2(det, dot) * 180 / np.pi
        return agent_next_node, ol, agent_dir

    def move_agent(self, t_now, new_cls, new_cle, new_status):
        self.cls = new_cls
        self.cle = new_cle
        self.status = new_status
        self.cl_enter_time = t_now

    def get_path(self, g=None):
        sp = g.dijkstra(self.cle, self.destin_nid)
        sp_dist = sp.distance(self.destin_nid)

        if sp_dist > 10e7:
            sp.clear()
            self.route_igraph = []
            return 'no_path_found'
        else:
            sp_route = sp.route(self.destin_nid)
            self.route_igraph = [(self.cls, self.cle)] + [(start_nid, end_nid) for (start_nid, end_nid) in sp_route]
            sp.clear()
            return 'path_found'


class Simulation:
    def __init__(self, NodeClass=Node, LinkClass=Link):
        self.g = None
        self.all_nodes = dict()
        self.all_links = dict()
        self.node_to_link_dict = dict()
        self.all_agents = dict()
        assert issubclass(NodeClass, Node), 'arg: NodeClass, must submit Node class that is a Node'
        assert issubclass(LinkClass, Link), 'arg: LinkClass, must submit Link class that is a Link'
        self.NodeClass = NodeClass
        self.LinkClass = LinkClass

    def create_network(self, nodes_df, links_df):
        ### create graph
        links_df['capacity'] = links_df['lanes'] * 1000
        links_df['fft'] = np.where(links_df['lanes']<=0, 1e8, links_df['length']/links_df['maxmph']*2.2369)
        self.g = interface.from_dataframe(links_df, 'start_node_id', 'end_node_id', 'fft')

        ### Create link and node objects
        nodes = []
        links = []
        for row in nodes_df.itertuples():
            real_node = self.NodeClass(row.node_id, row.lon, row.lat, row.type, row.node_osmid)
            virtual_node = real_node.create_virtual_node()
            virtual_link = real_node.create_virtual_link()
            nodes.append(real_node)
            nodes.append(virtual_node)
            links.append(virtual_link)
        for row in links_df.itertuples():
            real_link = self.LinkClass(row.link_id, row.lanes, row.length, row.fft, row.capacity, row.type, row.start_node_id, row.end_node_id, row.geometry, simulation=self)
            links.append(real_link)

        ### dictionaries for quick look-up
        self.node2link_dict = {(link.start_nid, link.end_nid): link.lid for link in links}
        self.all_links = {link.lid: link for link in links}
        self.all_nodes = {node.nid: node for node in nodes}
        for link_id, link in self.all_links.items():
            self.all_nodes[link.start_nid].out_links.append(link_id)
            self.all_nodes[link.end_nid].in_links[link_id] = None
        for node in self.all_nodes.values():
            node.calculate_straight_ahead_links(node_id_dict=self.all_nodes, link_id_dict=self.all_links)

    def create_demand(self, od_df):

        if 'agent_id' not in od_df.columns: od_df['agent_id'] = np.arange(od_df.shape[0])
        od_df['dept_time'] = 0
        od_df['veh_len'] = 8
        od_df['gps_reroute'] = 0
        od_df = od_df.sample(frac=1).reset_index(drop=True) ### randomly shuffle rows
        # print('# trips {}'.format(od_df.shape[0]))

        for row in od_df.itertuples():
            self.all_agents[row.agent_id] = Agent(row.agent_id, row.origin_node_id, row.destin_node_id, row.dept_time, row.veh_len, row.gps_reroute)


