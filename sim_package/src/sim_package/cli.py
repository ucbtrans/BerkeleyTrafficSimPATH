from runner import Runner
import argparse


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='command line tool for running spatial queue model')
    parser.add_argument('--nodes', required=True, help='path to nodes csv that represents all the intersections of your model')
    parser.add_argument('--links', required=True, help='path to link csv')
    parser.add_argument('--ods', required=True, help='path to travel demand csv')
    parser.add_argument('--name', default='berkeley-evac', help='path to travel demand csv')
    args = parser.parse_args()

    runner = Runner(args.links, args.nodes, args.ods)
    runner.init_sq_simulation()
    runner.spatial_queue_simulation(args.name)
