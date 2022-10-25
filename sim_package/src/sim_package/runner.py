from .queue_model import Simulation, Node, Link
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor
import argparse


class Runner:
    def __init__(self,
                 links_csv: str, nodes_csv: str, od_csv: str,
                 contraflow_csv='',
                 NodeClass=Node, LinkClass=Link, reroute_freq=10800):
        self.nodes_df = pd.read_csv(nodes_csv)
        self.links_df = pd.read_csv(links_csv)
        self.od_df = pd.read_csv(od_csv)
        self.sim = Simulation(NodeClass, LinkClass)
        self.reroute_freq = reroute_freq
        self.running = True

        if contraflow_csv:
            contraflow_df = pd.read_csv(contraflow_csv)
            self.links_df = self.links_df.merge(
                contraflow_df[['link_id', 'new_lanes']], how='left', on='link_id')

    def init_sq_simulation(self):
        self.sim.create_network(self.nodes_df, self.links_df)
        self.sim.create_demand(self.od_df)

        # remove vehicles from self.sim w/o path to the end
        cannot_find_path = []
        for vehicle_id, vehicle in self.sim.all_agents.items():
            routing_status = vehicle.get_path(g=self.sim.g)
            if routing_status == 'no_path_found':
                cannot_find_path.append(vehicle_id)

        [self.sim.all_agents.pop(vh_id) for vh_id in cannot_find_path]

        print(
            f'# o-d pairs whose paths cannot be found: {len(cannot_find_path)}')
        print(f'# o-d pairs/trips {len(self.sim.all_agents)}')

    def single_step_sq_sim(self, t):
        # load agents
        for agent in self.sim.all_agents.values():
            agent.load_trips(t)
            # reroute
            if t > 0 and t % self.reroute_freq == 0:
                agent.get_path(g=self.sim.g)
        # run link model
        for link in self.sim.all_links.values():
            link.run_link_model(t)
        # run node model
        node_ids_to_run = {
            link.end_nid for link in self.sim.all_links.values() if len(link.queue_veh) > 0}

        for nid in node_ids_to_run:
            node = self.sim.all_nodes[nid]
            node.run_node_model(t)

    # count the number of evacuees that have successfully reach their destination

    def arrival_counts(self, t, save_path):
        arrival_cnts = np.sum(
            [1 for a in self.sim.all_agents.values() if a.status == 'arr'])
        print(
            f'At {t} seconds, {arrival_cnts} evacuees successfully reached the destination.')
        if arrival_cnts == len(self.sim.all_agents):
            print(f"All agents arrive at destinations at time {t} seconds.")
            self.running = False
            return False
        with open(save_path, 'a') as t_stats_outfile:
            t_stats_outfile.write(f"{t},{arrival_cnts}\n")
        return True

    def write_link_outputs(self, save_path):
        link_output = pd.DataFrame([(link.lid, len(link.queue_veh), len(link.run_veh), np.round((len(link.queue_veh) + len(link.run_veh)) / (link.length * link.lanes+0.00001) * 100, 2), link.geometry)
                                   for link in self.sim.all_links.values() if link.ltype[0:2] != 'vl'], columns=['link_id', 'queue_vehicle_count', 'run_vehicle_count', 'vehicle_per_100m', 'geometry'])
        link_output = link_output[(link_output['queue_vehicle_count'] > 0) | (
            link_output['run_vehicle_count'] > 0)].reset_index(drop=True)
        link_output.to_csv(save_path, index=False)

    def write_node_outputs(self, save_path):
        node_predepart = pd.DataFrame([(agent.cle, 1) for agent in self.sim.all_agents.values() if (agent.status in [
                                      None, 'loaded'])], columns=['node_id', 'predepart_cnt']).groupby('node_id').agg({'predepart_cnt': np.sum}).reset_index()
        if node_predepart.shape[0] > 0:
            node_predepart = node_predepart.merge(
                self.nodes_df[['node_id', 'lat', 'lon']], how='left', on='node_id')
            node_predepart.to_csv(save_path, index=False)

    def spatial_queue_simulation(self, scenario_name, t_end=10801, output_dir='traffic_outputs'):
        arrival_output_path = f'{output_dir}/t_stats/arrivals_{scenario_name}.csv'
        with open(arrival_output_path, 'w') as t_stats_outfile:
            t_stats_outfile.write("t,arrival_count"+"\n")

        # iterate through each time step
        for t in range(t_end):
            # run the spatial-queue simulation for one step
            self.single_step_sq_sim(t)
            # break if all agents have reached their destinations
            if not self.running:
                return
            # output time-step results every 100 seconds
            if t % 100 == 0 and self.arrival_counts(t, arrival_output_path):
                link_output_path = f'{output_dir}/link_stats/l{scenario_name}_at_{t}.csv'
                node_output_path = f'{output_dir}/node_stats/n{scenario_name}_at_{t}.csv'
                self.write_link_outputs(link_output_path)
                self.write_node_outputs(node_output_path)


def cli():
    parser = argparse.ArgumentParser(
        description='command line tool for running spatial queue model')
    parser.add_argument('--nodes', required=True,
                        help='path to nodes csv that represents all the intersections of your model')
    parser.add_argument('--links', required=True, help='path to link csv')
    parser.add_argument('--ods', required=True,
                        help='path to travel demand csv')
    parser.add_argument(
        '--cf', help='path to contraflow links csv', default='')
    parser.add_argument('--name', default='berkeley-evac',
                        help='path to travel demand csv')
    args = parser.parse_args()

    runner = Runner(args.links, args.nodes, args.ods, args.cf)
    runner.init_sq_simulation()
    runner.spatial_queue_simulation(args.name)
