"""
This class ensures that the experiments are reproducible and that the results are catalogued in a consistent manner.

Reproducibility: 
    - The default hyperparameters are set for each model and a function to read hyperparameters from json is provided.
    - A function to save the hyperparameters in an experiment-run folder is provided. The experiment naming scheme 
      is also defined. 
    - A function to set the random seed is provided. The seed is set as a function of the experiment run number so 
      that the experiments can be run on different machines in parallel. 
"""
import os 
import json 
from dataclasses import dataclass, field, fields, asdict
from itertools import product 
from lightning.pytorch import seed_everything
from mdgp.experiment_utils import ModelArguments, DataArguments, TrainingArguments
from enum import Enum


__all__ = [
    'ExperimentConfig',
    'ExperimentStatus',
    'ExperimentConfigReader',
    'create_experiment_config',
    'create_experiment_config_from_json',
    'set_experiment_seed',
]


# TODO Move to utils
def non_default_fields(dc) -> dict:
    """
    Given a dataclass instance, return a dictionary containing 
    all the fields whose values are different from their defaults.

    Parameters:
    - dc: An instance of a dataclass.

    Returns:
    - Dict[str, Any]: Dictionary with fields and values different from defaults.
    """
    result = {}
    for field in fields(dc):
        current_value = getattr(dc, field.name)        
        if current_value != field.default:
            result[field.name] = current_value
    return result


# TODO Move to ExperimentConfig
def get_experiment_name(data_arguments, training_arguments, model_arguments) -> str:
    """
    Given a set of data, training and model arguments, return a string 
    containing the experiment name.

    Parameters:
    - data_arguments: An instance of the DataArguments dataclass.
    - training_arguments: An instance of the TrainingArguments dataclass.
    - model_arguments: An instance of the ModelArguments dataclass.

    Returns:
    - str: The experiment name.
    """
    data_arguments_dict = non_default_fields(data_arguments)
    training_arguments_dict = non_default_fields(training_arguments)
    model_arguments_dict = non_default_fields(model_arguments)
    all_arguments_dict = {**model_arguments_dict, **data_arguments_dict, **training_arguments_dict}

    # Verify that no arguments names are repeated 
    if len(all_arguments_dict) != len(data_arguments_dict) + len(training_arguments_dict) + len(model_arguments_dict):
        raise ValueError('There are repeated argument names between data, training, and model arguments')

    # If there are no arguments, return 'default'
    if len(all_arguments_dict) == 0: 
        return 'default'
    
    # Otherwise, return a string with all the arguments
    return '-'.join([f'{key}={value}' for key, value in all_arguments_dict.items()])


class ExperimentStatus(Enum): 
    READY = 'ready'
    RUNNING = 'running'
    FAILED = 'failed'
    COMPLETED = 'completed'


@dataclass 
class ExperimentConfig:
    """
    A dataclass that contains the configuration for an experiment. 
    """
    model_arguments: ModelArguments = field(default_factory=ModelArguments, metadata={'help': 'The model arguments.'})
    data_arguments: DataArguments = field(default_factory=DataArguments, metadata={'help': 'The data arguments.'})
    training_arguments: TrainingArguments = field(default_factory=TrainingArguments, metadata={'help': 'The training arguments.'})
    run: int = field(default=0, metadata={'help': 'The run number of the experiment.'})
    status: ExperimentStatus = field(default=ExperimentStatus.READY, metadata={'help': 'The status of the experiment.'})
    file_name: str = field(default='config.json', metadata={'help': 'The name of the config file.'})

    @property
    def seed(self):
        return self.run
    
    @property 
    def experiment_name(self):
        return get_experiment_name(self.data_arguments, self.training_arguments, self.model_arguments)
    
    @property 
    def run_name(self):
        return f"run_{self.run}"
    
    def to_dict(self): 
        return {
            'model_arguments': asdict(self.model_arguments),
            'data_arguments': asdict(self.data_arguments),
            'training_arguments': asdict(self.training_arguments),
            'run': self.run,
            'status': self.status.value,
        }
    
    def to_json(self, dir_path):
        file_path = os.path.join(dir_path, self.file_name)
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=4)

    @classmethod
    def from_dict(cls, data):
        data['status'] = ExperimentStatus(data['status'])
        data['model_arguments'] = ModelArguments(**data['model_arguments'])
        data['data_arguments'] = DataArguments(**data['data_arguments'])
        data['training_arguments'] = TrainingArguments(**data['training_arguments'])
        return cls(**data)

    @classmethod
    def from_json(cls, file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
            data['file_name'] = os.path.basename(file_path)
        return cls.from_dict(data)


def set_experiment_seed(run: int) -> None:
    seed_everything(run, workers=True)


# TODO Move to utils
def expand_args(args_dict):
    """
    Converts a dictionary of arguments into a list of dictionaries where each dictionary is a unique 
    combination of arguments.
    """
    keys = args_dict.keys()
    values = (args_dict[key] if isinstance(args_dict[key], list) else [args_dict[key]] for key in keys)
    return [dict(zip(keys, combination)) for combination in product(*values)]


def create_experiment_config_from_json(json_config, dir_path, overwrite=False) -> None:
    """
    Creates a folder for each experiment and a config file for each run. 

    Parameters:
    - json_config (dict): A dictionary containing the experiment configurations.
    - dir_path (str): The path to the parent directory where the experiment folders will be created.
    """

    # Expand arguments to get all possible configurations
    model_args_list = expand_args(json_config['model_arguments'])
    data_args_list = expand_args(json_config['data_arguments'])
    training_args_list = expand_args(json_config['training_arguments'])
    runs = json_config['runs']

    # Get all combinations of arguments
    for model_args, data_args, training_args in product(model_args_list, data_args_list, training_args_list):
        for run in runs:
            config = ExperimentConfig(
                model_arguments=ModelArguments(**model_args),
                data_arguments=DataArguments(**data_args),
                training_arguments=TrainingArguments(**training_args),
                run=run,
            )

            # Create experiment directory if it doesn't exist
            experiment_path = os.path.join(dir_path, config.experiment_name)
            os.makedirs(experiment_path, exist_ok=True)

            # Create run directory if doesn't exist 
            run_path = os.path.join(experiment_path, config.run_name)
            os.makedirs(run_path, exist_ok=True)

            # Maybe skip if config file already exists
            config_path = os.path.join(run_path, config.file_name)
            if os.path.exists(config_path) and not overwrite: 
                continue 
            
            # Save config file 
            config.to_json(run_path)


def create_experiment_config(json_config_path, dir_path, overwrite=False) -> None: 
    """
    Creates a folder for each experiment and a config file for each run. 

    Parameters:
    - dir_path (str): The path to the parent directory where the experiment folders will be created.
    - json_config_path (str): The path to the JSON file containing the experiment configurations.
    """

    # Read the JSON file
    with open(json_config_path, 'r') as f:
        json_config = json.load(f)
    
    create_experiment_config_from_json(json_config, dir_path, overwrite=overwrite)


class ExperimentConfigReader:
    def __init__(self, file_path, overwrite=False):
        self.file_path = file_path
        self.overwrite = overwrite
        self.experiment_config = None

    def __enter__(self):
        # This part is executed when entering the 'with' block
        self.experiment_config = ExperimentConfig.from_json(self.file_path)
        if (self.experiment_config.status == ExperimentStatus.READY or 
            self.experiment_config.status == ExperimentStatus.FAILED or 
            (self.experiment_config.status == ExperimentStatus.COMPLETED and self.overwrite)):
            self._update_status(ExperimentStatus.RUNNING)
        return self.experiment_config

    def __exit__(self, exc_type, exc_value, traceback):
        if self.experiment_config.status == ExperimentStatus.RUNNING:
            status = ExperimentStatus.COMPLETED if exc_type is None else ExperimentStatus.FAILED
            self._update_status(status)

    def _update_status(self, status):
        # Instead of directly modifying the JSON, we update the ExperimentConfig object and save it
        self.experiment_config.status = status
        self.experiment_config.to_json(os.path.dirname(self.file_path))
