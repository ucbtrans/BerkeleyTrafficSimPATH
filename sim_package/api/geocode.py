from psutil import virtual_memory
import requests
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.wkt import loads
from shapely import wkt
import osmnx as ox
import os
import time


# def get_location_coordinates(location):
#     address = location.replace(",", "+")
#     geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GEOCODE_API_KEY}"
#     response = requests.get(geo_url)
#     content = response.content.decode("utf8")
#     geo_js = json.loads(content)
#     geo_status = geo_js["status"]

#     if geo_status == "OK":
#         geo_elements = geo_js["results"][0]
#         geometry = geo_elements["geometry"]
#         location_coordinates = geometry["location"]
#         location_lat = location_coordinates["lat"]
#         location_long = location_coordinates["lng"]
#         print(f"Long/lat coordinates successfully extracted.")
#     else:
#         location_lat = "Unavailable"
#         location: long = "Unavailable"
#         print(f"Long/lat coordinates unavailable.")
#     return location_lat, location_long


# def create_graph(location_lat, location_long, diameter):
#     dist = diameter
#     point = location_lat, location_long
#     G = ox.graph_from_point(
#         point, dist=dist, network_type='drive', simplify=False)
#     return G


# def convert_to_geopandas(G):
#     return ox.graph_to_gdfs(G)


# def rearrange_data(ox_nodes, ox_edges):
#     raw_nodes = ox_nodes.copy().reset_index()
#     raw_nodes['node_id'] = np.arange(raw_nodes.shape[0])
#     raw_nodes['lon'] = raw_nodes['x']
#     raw_nodes['lat'] = raw_nodes['y']
#     raw_nodes["node_osmid"] = raw_nodes["osmid"]
#     raw_nodes["type"] = ["real" for i in range(raw_nodes.shape[0])]

#     osmid_to_nid_dict = {getattr(node, 'osmid'): getattr(
#         node, 'node_id') for node in raw_nodes.itertuples()}
#     raw_edges = ox_edges.copy().reset_index()
#     raw_edges['link_id'] = np.arange(raw_edges.shape[0])
#     raw_edges['start_node_id'] = raw_edges['u'].map(osmid_to_nid_dict)
#     raw_edges['end_node_id'] = raw_edges['v'].map(osmid_to_nid_dict)
#     raw_edges['start_osmid'] = raw_edges['u']
#     raw_edges['end_osmid'] = raw_edges['v']
#     raw_edges["type"] = raw_edges["highway"]
#     raw_edges['length'] = raw_edges['length'].astype(float)
#     raw_edges['lanes'] = raw_edges['lanes'].fillna(
#         '1').apply(lambda x: take_average(x))
#     raw_edges['maxmph'] = raw_edges['maxspeed'].fillna(
#         '25').apply(lambda x: take_average(x))
#     raw_edges['geometry'] = raw_edges['geometry'].apply(wkt.dumps)
#     raw_edges['capacity'] = raw_edges['lanes'] * 1000

#     # make a random node virtual node - exit node
#     virtual_node_id = raw_nodes.sample(
#         n=1, random_state=31).node_id.values[0]
#     print(virtual_node_id)
#     raw_nodes.loc[raw_nodes['node_id']
#                   == virtual_node_id, 'type'] = 'vn_sink'
#     raw_nodes.loc[raw_nodes['node_id'] ==
#                   virtual_node_id, 'node_osmid'] = 'vn_sink'

#     raw_edges.loc[raw_edges['end_node_id'] ==
#                   virtual_node_id, 'type'] = 'vl_out'
#     raw_edges.loc[raw_edges['end_node_id'] ==
#                   virtual_node_id, 'end_osmid'] = 'vn_sink'
#     raw_edges.loc[raw_edges['end_node_id'] ==
#                   virtual_node_id, 'maxmph'] = '1000.0'
#     raw_edges.loc[raw_edges['end_node_id'] ==
#                   virtual_node_id, 'capacity'] = '1000000'
#     raw_edges.loc[raw_edges['end_node_id']
#                   == virtual_node_id, 'lanes'] = '1000'

#     raw_edges.reset_index()

#     raw_nodes = raw_nodes.drop(
#         ['x', 'y', 'street_count', 'ref', 'geometry', 'highway', 'osmid'], axis=1)
#     raw_edges = raw_edges[['link_id', 'start_node_id', 'end_node_id', 'type',
#                            'length', 'maxmph', 'lanes', 'capacity', 'start_osmid', 'end_osmid', 'geometry']]

#     return raw_nodes, raw_edges, virtual_node_id


# def get_csv_from_location_name(location):
#     # location_lat, location_long = get_location_coordinates(location)
#     case = location
#     startGrahphTime = time.time()
#     G = ox.graph_from_place(location, network_type="drive")
#     ox_nodes, ox_edges = convert_to_geopandas(G)
#     finishGrahphTime = time.time()
#     print("Graph creation time: ", finishGrahphTime - startGrahphTime)
#     raw_nodes, raw_edges = rearrange_data(ox_nodes, ox_edges)
#     removed_edges = raw_edges[raw_edges['length'] <= 20].copy()
#     removed_node_grp = {}
#     grp_id = 0
#     for edge in removed_edges.itertuples():
#         nid_s = getattr(edge, 'nid_s')
#         nid_e = getattr(edge, 'nid_e')
#         try:
#             nid_s_grp = removed_node_grp[nid_s]
#         except KeyError:
#             nid_s_grp = grp_id
#         try:
#             nid_e_grp = removed_node_grp[nid_e]
#         except KeyError:
#             nid_e_grp = grp_id
#         nid_se_grp_id = min(nid_s_grp, nid_e_grp)
#         removed_node_grp[nid_s] = nid_se_grp_id
#         removed_node_grp[nid_e] = nid_se_grp_id
#         if nid_se_grp_id == grp_id:
#             grp_id += 1

#     removed_node_grp_df = pd.DataFrame(
#         removed_node_grp.items(), columns=['nid', 'node_grp'])
#     removed_node_grp_df['node_grp'] = removed_node_grp_df['node_grp'].apply(
#         lambda x: 'g{}'.format(x))
#     print(' ... when edges < 20m are removed, {} nodes are removed along, and {} virtual nodes are generated'.format(
#         removed_node_grp_df['nid'].nunique(), removed_node_grp_df['node_grp'].nunique()))

#     # contract edges
#     # remove those with duplicated new_node_id, e.g., becoming loops
#     contracted_edges = raw_edges.copy()
#     contracted_edges = pd.merge(contracted_edges, removed_node_grp_df,
#                                 how='left', left_on='nid_s', right_on='nid')
#     contracted_edges = pd.merge(contracted_edges, removed_node_grp_df,
#                                 how='left', left_on='nid_e', right_on='nid', suffixes=['_ns0', '_ne0'])
#     contracted_edges['node_grp_ns0'] = np.where(
#         pd.isnull(contracted_edges['node_grp_ns0']), contracted_edges['nid_s'], contracted_edges['node_grp_ns0'])
#     contracted_edges['node_grp_ne0'] = np.where(
#         pd.isnull(contracted_edges['node_grp_ne0']), contracted_edges['nid_e'], contracted_edges['node_grp_ne0'])
#     contracted_edges = contracted_edges[[
#         'nid_s', 'nid_e', 'node_grp_ns0', 'node_grp_ne0', 'length', 'lanes', 'maxspeed', 'geometry'
#     ]]
#     contracted_edges = contracted_edges.loc[contracted_edges['node_grp_ns0']
#                                             != contracted_edges['node_grp_ne0']]

#     # contract nodes
#     contracted_nodes = pd.merge(
#         raw_nodes, removed_node_grp_df, how='left', on='nid')
#     contracted_nodes['node_grp'] = np.where(
#         pd.isnull(contracted_nodes['node_grp']), contracted_nodes['nid'], contracted_nodes['node_grp'])
#     contracted_nodes = contracted_nodes.groupby('node_grp').agg(
#         {'lon': np.mean, 'lat': np.mean, }).reset_index()
#     print('Originally there are {} nodes; now there are {} nodes'.format(
#         raw_nodes.shape[0], contracted_nodes.shape[0]))
#     # update nodes
#     contracted_nodes = contracted_nodes.loc[(
#         contracted_nodes['node_grp'].isin(contracted_edges['node_grp_ns0'])) |
#         (contracted_nodes['node_grp'].isin(contracted_edges['node_grp_ne0']))
#     ]
#     contracted_nodes['node_id'] = np.arange(contracted_nodes.shape[0])

#     contracted_edges = pd.merge(contracted_edges, contracted_nodes,
#                                 how='left', left_on='node_grp_ns0', right_on='node_grp')
#     contracted_edges = pd.merge(contracted_edges, contracted_nodes,
#                                 how='left', left_on='node_grp_ne0', right_on='node_grp',
#                                 suffixes=['_ns', '_ne'])
#     print('Some nodes and links in newly formed loops are further removed, resulting in {} nodes and {} edges'.format(
#         contracted_nodes.shape[0], contracted_edges.shape[0]))

#     # update geometry
#     geometry_list = []
#     for edge in contracted_edges.itertuples():
#         geometry = getattr(edge, 'geometry').replace(
#             'LINESTRING(', '').replace(')', '').split(', ')
#         geometry = [tuple(xy.split(' ')) for xy in geometry]
#         lon_ns, lat_ns = getattr(edge, 'lon_ns'), getattr(edge, 'lat_ns')
#         lon_ne, lat_ne = getattr(edge, 'lon_ne'), getattr(edge, 'lat_ne')
#         geometry = [(lon_ns, lat_ns)] + geometry[1:-2] + [(lon_ne, lat_ne)]
#         geometry_list.append(
#             'LINESTRING('+', '.join('{} {}'.format(xy[0], xy[1]) for xy in geometry)+')')
#     contracted_edges['geometry'] = geometry_list
#     contracted_edges['start_nid'] = contracted_edges['node_id_ns']
#     contracted_edges['end_nid'] = contracted_edges['node_id_ne']
#     contracted_edges['nid_s_old'] = contracted_edges['nid_s']
#     contracted_edges['nid_e_old'] = contracted_edges['nid_e']
#     contracted_edges = contracted_edges[['start_nid', 'end_nid', 'nid_s_old', 'nid_e_old',
#                                         'length', 'lanes', 'maxspeed', 'geometry']]
#     contracted_edges = contracted_edges.loc[contracted_edges['start_nid']
#                                             != contracted_edges['end_nid']]

#     # add attributes (speed in mph)
#     contracted_edges['maxmph'] = contracted_edges['maxspeed']
#     contracted_edges['fft'] = contracted_edges['length'] / \
#         (contracted_edges['maxmph']*1609/3600)
#     contracted_edges = contracted_edges.sort_values(by='fft', ascending=True).drop_duplicates(
#         subset=['start_nid', 'end_nid'], keep='first')
#     print('Some links that connect the same pair of nodes are further removed, resulting in {} nodes and {} edges'.format(
#         contracted_nodes.shape[0], contracted_edges.shape[0]))

#     # add link_id
#     contracted_edges['link_id'] = np.arange(contracted_edges.shape[0])
#     contracted_edges = contracted_edges.reset_index(drop=True)
#     contracted_nodes = contracted_nodes.reset_index(drop=True)

#     removed_node_grp_df.to_csv(
#         '{}_nid_grp_conversion.csv'.format(case), index=False)
#     raw_nodes.to_csv('{}_nodes.csv'.format(case), index=False)
#     raw_edges.to_csv('{}_links.csv'.format(case), index=False)
#     ox.plot_graph(G)
#     return "Success"


# def create_fake_demand(demand_from_each_node, raw_nodes, destin_id):
#     df = pd.DataFrame(
#         columns=['origin_node_id', 'destin_node_id', 'origin_osmid', 'destin_osmid'])
#     for id, row in raw_nodes.iterrows():
#         for i in range(demand_from_each_node):
#             df = pd.concat([df, pd.DataFrame.from_records([{'origin_node_id': row['node_id'], 'destin_node_id': destin_id,
#                             'origin_osmid': row['node_osmid'], 'destin_osmid': 'vn_sink'}])], ignore_index=True)

#     return df


# def get_csv_from_location_name_without_virtual_nodes(location):
#     # location_lat, location_long = get_location_coordinates(location)
#     case = location.lower().replace(" ", "_").replace(',', "")
#     startGrahphTime = time.time()
#     G = ox.graph_from_place(location, network_type="drive")
#     ox_nodes, ox_edges = convert_to_geopandas(G)
#     finishGrahphTime = time.time()
#     print("Graph creation time: ", finishGrahphTime - startGrahphTime)
#     raw_nodes, raw_edges, virtual_node_id = rearrange_data(ox_nodes, ox_edges)
#     new_df = create_fake_demand(5, raw_nodes, virtual_node_id)  # do better
#     new_df.to_csv('{}_od.csv'.format(case), index=False)
#     raw_nodes.to_csv('{}_nodes.csv'.format(case), index=False)
#     raw_edges.to_csv('{}_links.csv'.format(case), index=False)
#     ox.plot_graph(G)
#     # FAKE DEMAND
#     return "Success"


# get_csv_from_location_name_without_virtual_nodes("Eureka, California")


class Location:

    def take_average(self, x):
        if isinstance(x, list):
            return np.mean([int(xi.split(' ')[0]) for xi in x])
        else:
            return int(x.split(' ')[0])

    def __init__(self, location):
        self.case = location.lower().replace(" ", "_").replace(',', "")
        self.graph = []
        self.location = location
        self.nodesOX = []
        self.edgesOX = []
        self.nodes = []
        self.edges = []
        self.virtual_node_id = 0
        self.demand_from_each_node = 5
        self.demand = []
        self.path = "traffic_inputs"

    def set_edges_nodes(self, location):
        startGrahphTime = time.time()
        self.graph = ox.graph_from_place(location, network_type="drive")
        self.nodesOX, self.edgesOX = ox.graph_to_gdfs(self.graph)
        finishGrahphTime = time.time()
        print("Graph creation time: ", finishGrahphTime - startGrahphTime)

    def rearrange_data(self):
        raw_nodes = self.nodesOX.copy().reset_index()
        raw_nodes['node_id'] = np.arange(raw_nodes.shape[0])
        raw_nodes['lon'] = raw_nodes['x']
        raw_nodes['lat'] = raw_nodes['y']
        raw_nodes["node_osmid"] = raw_nodes["osmid"]
        raw_nodes["type"] = ["real" for i in range(raw_nodes.shape[0])]

        osmid_to_nid_dict = {getattr(node, 'osmid'): getattr(
            node, 'node_id') for node in raw_nodes.itertuples()}
        raw_edges = self.edgesOX.copy().reset_index()
        raw_edges['link_id'] = np.arange(raw_edges.shape[0])
        raw_edges['start_node_id'] = raw_edges['u'].map(osmid_to_nid_dict)
        raw_edges['end_node_id'] = raw_edges['v'].map(osmid_to_nid_dict)
        raw_edges['start_osmid'] = raw_edges['u']
        raw_edges['end_osmid'] = raw_edges['v']
        raw_edges["type"] = raw_edges["highway"]
        raw_edges['length'] = raw_edges['length'].astype(float)
        raw_edges['lanes'] = raw_edges['lanes'].fillna(
            '1').apply(lambda x: self.take_average(x))
        raw_edges['maxmph'] = raw_edges['maxspeed'].fillna(
            '25').apply(lambda x: self.take_average(x))
        raw_edges['geometry'] = raw_edges['geometry'].apply(wkt.dumps)
        raw_edges['capacity'] = raw_edges['lanes'] * 1000

        # make a random node virtual node - exit node
        virtual_node_id = raw_nodes.sample(
            n=1, random_state=31).node_id.values[0]

        raw_nodes.loc[raw_nodes['node_id']
                      == virtual_node_id, 'type'] = 'vn_sink'
        raw_nodes.loc[raw_nodes['node_id'] ==
                      virtual_node_id, 'node_osmid'] = 'vn_sink'

        raw_edges.loc[raw_edges['end_node_id'] ==
                      virtual_node_id, 'type'] = 'vl_out'
        raw_edges.loc[raw_edges['end_node_id'] ==
                      virtual_node_id, 'end_osmid'] = 'vn_sink'
        raw_edges.loc[raw_edges['end_node_id'] ==
                      virtual_node_id, 'maxmph'] = '1000.0'
        raw_edges.loc[raw_edges['end_node_id'] ==
                      virtual_node_id, 'capacity'] = '1000000'
        raw_edges.loc[raw_edges['end_node_id']
                      == virtual_node_id, 'lanes'] = '1000'

        raw_edges.reset_index()

        raw_nodes = raw_nodes.drop(
            ['x', 'y', 'street_count', 'geometry', 'highway', 'osmid'], axis=1)
        raw_edges = raw_edges[['link_id', 'start_node_id', 'end_node_id', 'type',
                               'length', 'maxmph', 'lanes', 'capacity', 'start_osmid', 'end_osmid', 'geometry']]
        self.nodes = raw_nodes
        self.edges = raw_edges
        self.virtual_node_id = virtual_node_id

    def create_demand(self):
        df = pd.DataFrame(
            columns=['origin_node_id', 'destin_node_id', 'origin_osmid', 'destin_osmid'])
        for id, row in self.nodes.iterrows():
            for i in range(self.demand_from_each_node):
                df = pd.concat([df, pd.DataFrame.from_records([{'origin_node_id': row['node_id'], 'destin_node_id': self.virtual_node_id,
                                'origin_osmid': row['node_osmid'], 'destin_osmid': 'vn_sink'}])], ignore_index=True)
        self.demand = df

    def save_data(self):
        print(self.path)
        self.demand.to_csv(os.path.join(
            os.getcwd(), self.path+'{}_od.csv'.format(self.case)), index=False)
        self.nodes.to_csv(os.path.join(
            os.getcwd(), self.path+'{}_nodes.csv'.format(self.case)), index=False)
        self.edges.to_csv(os.path.join(
            os.getcwd(), self.path+'{}_edges.csv'.format(self.case)), index=False)

    def plot_graph(self):
        ox.plot_graph(self.graph)

    def run(self):
        self.set_edges_nodes(self.location)
        self.rearrange_data()
        self.create_demand()
        self.save_data()
        self.plot_graph()
