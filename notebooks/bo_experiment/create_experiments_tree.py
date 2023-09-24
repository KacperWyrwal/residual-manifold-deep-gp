from argparse import ArgumentParser
from mdgp.bo_experiment import create_experiment_config 


if __name__ == '__main__':
    parser = ArgumentParser(description='Create experiment config files')
    parser.add_argument('--overwrite', default=False, action='store_true', help='Overwrite existing config files')
    parser.add_argument('--dir_path', type=str, default='../../experiments/bo', help='The directory to save the config files to')
    parser.add_argument('--config_path', type=str, default='../../experiment_tree_configs/bo/exact_ackley.json', help='The path to the config file to create')
    args = parser.parse_args()

    create_experiment_config(json_config_path=args.config_path, dir_path=args.dir_path, overwrite=args.overwrite)