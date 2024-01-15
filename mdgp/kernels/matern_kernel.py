from geometric_kernels.frontends.pytorch.gpytorch import GPytorchGeometricKernel
from geometric_kernels.kernels.matern_kernel import MaternGeometricKernel
from geometric_kernels.spaces import Space, Euclidean
from torch import Generator
from warnings import warn 
from gpytorch.kernels import MaternKernel
from geometric_kernels.types import FeatureMap
from geometric_kernels.kernels.matern_kernel import default_feature_map



class BaseMaternKernel:
    def __init__(self, space, seed: None | int = None): 
        # Set RNG randomly or with a seed
        key = Generator() 
        if seed is not None:
            key.manual_seed(seed)        
        self.seed = seed 
        self.key = key 
        self.feature_map = default_feature_map(space=space)


class _GeometricMaternKernel(BaseMaternKernel, GPytorchGeometricKernel): 
    def __init__(
        self, 
        space: Space, 
        lengthscale: float = 1.0,
        nu: float = 2.5,
        trainable_nu: bool = True,
        seed: int | None = None,
        num_random_phases: int | None = None, 
        num_eigenfunctions: int | None = None, 
        **kwargs, 
    ) -> None: 
        BaseMaternKernel.__init__(self, space=space, seed=seed)

        if num_random_phases is not None and num_eigenfunctions is not None:
            warn("Only one of num_random_phases and num_eigenfunctions will be used. You have passed both. Make sure this is intended.")
        base_kernel = MaternGeometricKernel(
            space=space, 
            num=num_random_phases or num_eigenfunctions, 
            normalize=True, 
            return_feature_map=False, 
            key=self.key, 
        )
        GPytorchGeometricKernel.__init__(self, base_kernel, lengthscale=lengthscale, nu=nu, 
                                         trainable_nu=trainable_nu, **kwargs)


from math import prod 
import torch 


class _EuclideanMaternKernel(BaseMaternKernel, MaternKernel):
    def __init__(
        self, 
        space: Euclidean, 
        lengthscale: float = 1.0,
        nu: float = 2.5,
        trainable_nu: bool = False,
        seed: int | None = None,
        **kwargs, 
    ) -> None: 
        assert trainable_nu is False, "Trainable nu is not yet supported for Euclidean spaces."
        BaseMaternKernel.__init__(self, space=space, seed=seed)
        MaternKernel.__init__(self, nu=nu, **kwargs)
        self.initialize(lengthscale=lengthscale) 
        self._batch_shape_scaling_factor = torch.tensor(1.)
        self.space = space 

    
    @property
    def batch_shape_scaling_factor(self):
        return self._batch_shape_scaling_factor

    @property
    def geometric_kernel_params(self):
        return {
            'lengthscale': self.lengthscale, 
            'nu': self.nu, 
        }


class GeometricMaternKernel: 
    def __new__(
        cls, 
        space: Space, 
        lengthscale: float = 1.0,
        nu: float = 2.5,
        trainable_nu: bool = True,
        seed: int | None = None,
        num_random_phases: int | None = None,
        num_eigenfunctions: int | None = None,
        **kwargs,
    ) -> _GeometricMaternKernel | _EuclideanMaternKernel: 
        if isinstance(space, Euclidean):
            return _EuclideanMaternKernel(space=space, lengthscale=lengthscale, nu=nu, trainable_nu=trainable_nu, seed=seed, **kwargs)
        return _GeometricMaternKernel(
            space=space, lengthscale=lengthscale, nu=nu, trainable_nu=trainable_nu, seed=seed, 
            num_random_phases=num_random_phases, num_eigenfunctions=num_eigenfunctions, **kwargs)

"""
class GeometricMaternKernel(GPytorchGeometricKernel): 

    def __init__(
        self, 
        space: Space, 
        lengthscale: float = 1.0,
        nu: float = 2.5,
        trainable_nu: bool = True,
        seed: int | None = None,
        num_random_phases: int | None = None, 
        num_eigenfunctions: int | None = None, 
        **kwargs, 
    ) -> None: 
        
        # Set RNG randomly or with a seed
        key = Generator()
        if seed is not None:
            key.manual_seed(seed)

        # If space is Euclidean the Matern kernel implementation from GPyTorch is most efficient.
        # Although it cannot handle trainable nu.
        if isinstance(space, Euclidean):
            assert trainable_nu is False, "Trainable nu is not supported for Euclidean spaces because GPyTorch MaternKernel is used."
            base_kernel = MaternKernel(nu=nu)
            base_kernel.initialize(lengthscale=lengthscale)
            feature_map = default_feature_map(space=space)
        # If space is not Euclidean, we use MaternGeometricKernel from GeometricKernels. 
        else: 
            if num_random_phases is not None and num_eigenfunctions is not None:
                warn("Only one of num_random_phases and num_eigenfunctions will be used. You have passed both. Make sure this is intended.")
            base_kernel, feature_map = MaternGeometricKernel(
                space=space, 
                num=num_random_phases or num_eigenfunctions, 
                normalize=True, 
                return_feature_map=True, 
                key=key, 
            )
        
        super().__init__(base_kernel, lengthscale=lengthscale, nu=nu, trainable_nu=trainable_nu, **kwargs)
        self._space = space 
        self._seed = seed 
        self._key = key 
        self._num_random_phases = num_random_phases
        self._num_eigenfunctions = num_eigenfunctions
        self._feature_map = feature_map

    @property
    def space(self) -> Space:
        return self._space

    @property
    def feature_map(self):
        return self._feature_map

    @property
    def seed(self) -> int | None:
        return self._seed
    
    @property 
    def key(self) -> Generator:
        return self._key
    
    @property
    def num_eigenfunctions(self) -> int:
        return self._num_eigenfunctions
    
    @property
    def num_random_phases(self) -> int:
        return self._num_random_phases
"""