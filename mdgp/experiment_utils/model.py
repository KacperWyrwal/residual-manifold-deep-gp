# Type hints
from torch import Tensor
from geometric_kernels.spaces import Space

# Imports 
from dataclasses import dataclass, field
from mdgp.utils import sphere_uniform_grid
from mdgp.models.deep_gps import GeometricManifoldDeepGP, EuclideanManifoldDeepGP, EuclideanDeepGP
from geometric_kernels.spaces import Hypersphere
from gpytorch.priors import GammaPrior


@dataclass
class ModelArguments:
    space_name: str = field(default='hypersphere', metadata={'help': 'The space where the data lives'})
    space_dim: int = field(default=2, metadata={'help': 'The dimension of the space where the data lives'})
    model_name: str = field(default='geometric_manifold', metadata={'help': 'Name of the model. Must be one of ["geometric_manifold", "euclidean_manifold", "euclidean"]'})
    num_hidden: int = field(default=1, metadata={'help': 'Number of hidden layers'})
    num_inducing: int = field(default=60, metadata={'help': 'Number of inducing points'})
    num_eigenfunctions: int = field(default=20, metadata={'help': 'Number of eigenfunctions to use'})
    learn_inducing_locations: bool = field(default=False, metadata={'help': 'Whether to learn the inducing locations'})
    optimize_nu: bool = field(default=True, metadata={'help': 'Whether to optimize the smoothness parameter'})
    nu: float = field(default=2.5, metadata={'help': 'Smoothness parameter'})
    tangent_to_manifold: str = field(default='exp', metadata={'help': 'Name of the function to map from the tangent space to the manifold. Must be one of ["exp", "log"]'})
    project_to_tangent: str = field(default='intrinsic', metadata={'help': 'Name of the function to map from the manifold to the tangent space. Must be one of ["intrinsic", "extrinsic"]'})
    parametrised_frame: bool = field(default=False, metadata={'help': 'Whether to use a parametrised frame'})
    rotated_frame: bool = field(default=False, metadata={'help': 'Whether to use a rotated frame'})
    outputscale_mean: float = field(default=1.0, metadata={'help': 'Mean of the outputscale'})

    @property 
    def space(self):
        if self.space_name == 'hypersphere':
            return Hypersphere(dim=self.space_dim)
        raise ValueError(f"Unknown space: {self.space_name}. Must be one of ['hypersphere'].")


def get_inducing_points(num_inducing: int, space: Space) -> Tensor:
    if isinstance(space, Hypersphere) and space.dim == 2:  
        return sphere_uniform_grid(num_inducing)
    raise ValueError(f"Unknown space: {space}. Must be one of [Hypersphere(dim=2)].")


def get_outputscale_prior(outputscale_mean: float = 1.0):
    return GammaPrior(concentration=1.0, rate=1 / outputscale_mean) 


def create_model(model_args: ModelArguments):
    space = Hypersphere(dim=2)
    inducing_points = sphere_uniform_grid(n=model_args.num_inducing)
    model_name = model_args.model_name
    outputscale_prior = get_outputscale_prior(outputscale_mean=model_args.outputscale_mean)
    if model_name == 'geometric_manifold':
        return GeometricManifoldDeepGP(
            space=space, 
            inducing_points=inducing_points, 
            outputscale_prior=outputscale_prior, 
            num_hidden=model_args.num_hidden, 
            num_eigenfunctions=model_args.num_eigenfunctions, 
            learn_inducing_locations=model_args.learn_inducing_locations, 
            optimize_nu=model_args.optimize_nu, 
            nu=model_args.nu,
            project_to_tangent=model_args.project_to_tangent, 
            tangent_to_manifold=model_args.tangent_to_manifold,
        )
    if model_name == 'euclidean_manifold': 
        return EuclideanManifoldDeepGP(
            space=space,
            inducing_points=inducing_points,
            outputscale_prior=outputscale_prior,
            num_hidden=model_args.num_hidden, 
            learn_inducing_locations=model_args.learn_inducing_locations, 
            nu=model_args.nu,
            project_to_tangent=model_args.project_to_tangent, 
            tangent_to_manifold=model_args.tangent_to_manifold,
        )
    if model_name == 'euclidean': 
        return EuclideanDeepGP(
            inducing_points=inducing_points, 
            outputscale_prior=outputscale_prior,
            num_hidden=model_args.num_hidden, 
            nu=model_args.nu, 
            learn_inducing_locations=model_args.learn_inducing_locations, 
        )
    raise ValueError(f"Unknown model name: {model_name}. Must be one of ['geometric_manifold', 'euclidean_manifold', 'euclidean']")
