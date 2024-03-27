from torch import Tensor 


import torch 
from gpytorch import settings
from gpytorch.variational import CholeskyVariationalDistribution
from gpytorch.models.deep_gps import DeepGPLayer, DeepGP
from gpytorch.kernels import ScaleKernel
from gpytorch.means import ConstantMean
from gpytorch.distributions import MultivariateNormal
from gpytorch.likelihoods import MultitaskGaussianLikelihood
from geometric_kernels.spaces import Hypersphere
from mdgp.experiments.uci.data.datasets import UCIDataset
from mdgp.kernels import GeometricMaternKernel
from mdgp.variational import SphericalHarmonicFeaturesVariationalStrategy
from mdgp.variational.spherical_harmonic_features.utils import total_num_harmonics, num_spherical_harmonics_to_num_levels
from mdgp.samplers import sample_elementwise


# Settings from the spherical harmonics paper 
LIKELIHOOD_VARIANCE = 1.0
LENGTHSCALE = 1.0
INNER_LAYER_VARIANCE = 1e-5 # This is from DSVI paper 
OUTPUT_LAYER_VARIANCE = 1.0 # This is a (reasonable) guess
# NUM_INDUCING_POINTS = 100 # This is from DSVI paper 
NUM_HARMONICS_KERNEL = 625 # Minimum number of harmonics to represent a kernel. Equivalent to 25 levels on S^2
NU = 1.5 # Should be inf to match DSVI, but will do for now 
OPTIMIZE_NU = False # False to match spherical harmonics paper


dimension_to_num_harmonics_variational = {
    4: 336,
    6: 294,
    8: 210,
}


import gpytorch 
from mdgp.samplers import sample_elementwise
from linear_operator.operators import BlockDiagLinearOperator


class DeepGPLayer(gpytorch.models.ApproximateGP):

    def __init__(self, variational_strategy, input_dims, output_dims):
        super(DeepGPLayer, self).__init__(variational_strategy)
        self.input_dims = input_dims
        self.output_dims = output_dims

    def forward(self, x):
        raise NotImplementedError

    def __call__(self, inputs, are_samples=False, **kwargs):
        if isinstance(inputs, gpytorch.distributions.MultitaskMultivariateNormal):
            inputs = sample_elementwise(inputs)
            are_samples = True 

        if gpytorch.settings.debug.on():
            if not torch.is_tensor(inputs):
                raise ValueError(
                    "`inputs` should either be a MultitaskMultivariateNormal or a Tensor, got "
                    f"{inputs.__class__.__Name__}"
                )

            if inputs.size(-1) != self.input_dims:
                raise RuntimeError(
                    f"Input shape did not match self.input_dims. Got total feature dims [{inputs.size(-1)}],"
                    f" expected [{self.input_dims}]"
                )

        # Repeat the input for all possible outputs
        if self.output_dims is not None:
            inputs = inputs.unsqueeze(-3) # No need to expand 

        # Now run samples through the GP
        output = gpytorch.models.ApproximateGP.__call__(self, inputs, **kwargs)
        if self.output_dims is not None:
            mean = output.loc.transpose(-1, -2)
            covar = BlockDiagLinearOperator(output.lazy_covariance_matrix, block_dim=-3)
            output = gpytorch.distributions.MultitaskMultivariateNormal(mean, covar, interleaved=False)

        # Maybe expand inputs?
        if not are_samples:
            # output = output.expand(torch.Size([gpytorch.settings.num_likelihood_samples.value()]) + output.shape)
            output = output.expand(torch.Size([gpytorch.settings.num_likelihood_samples.value()]) + output.batch_shape)

        return output


class SHFDeepGPLayer(DeepGPLayer):
    def __init__(
        self, 
        d, 
        hidden: bool,
        jitter_val: float | None = None, 
        optimize_nu: bool = True, 
        output_dims: int | None = None,
    ):
        max_ell = num_spherical_harmonics_to_num_levels(dimension_to_num_harmonics_variational[d], d)[0] # This is the spherical harmonics paper version 
        # max_ell = num_spherical_harmonics_to_num_levels(NUM_HARMONICS_KERNEL, d)[0] # This is the DSVI version
        max_ell_prior = num_spherical_harmonics_to_num_levels(NUM_HARMONICS_KERNEL, d)[0]
        m = total_num_harmonics(max_ell, d)

        batch_shape = torch.Size([]) if output_dims is None else torch.Size([output_dims])
        variational_distribution = CholeskyVariationalDistribution(num_inducing_points=m, batch_shape=batch_shape)
        variational_strategy = SphericalHarmonicFeaturesVariationalStrategy(self, variational_distribution, num_levels=max_ell, jitter_val=jitter_val)
        super().__init__(variational_strategy, d + 1, output_dims)
        self.batch_shape = batch_shape 

        # constants 
        self.jitter_val = jitter_val or settings.cholesky_jitter.value(torch.get_default_dtype())
        self.max_ell = max_ell
        self.max_ell_prior = max_ell_prior
        self.d = d

        # modules 
        base_kernel = GeometricMaternKernel(
            space=Hypersphere(d),
            lengthscale=LENGTHSCALE, 
            nu=NU, 
            trainable_nu=optimize_nu, 
            num_eigenfunctions=max_ell_prior,
            batch_shape=batch_shape,
        )
        self.covar_module = ScaleKernel(base_kernel, batch_shape=batch_shape)
        if hidden:
            self.covar_module.outputscale = INNER_LAYER_VARIANCE
        else:
            self.covar_module.outputscale = OUTPUT_LAYER_VARIANCE
        # Linear mean is equivalent to ConstantMean + expmap, which is done in DeepGP
        self.mean_module = ConstantMean(batch_shape=batch_shape)

    def forward(self, x: Tensor) -> MultivariateNormal:
        mean_x = self.mean_module(x)
        covar_x = self.covar_module(x)
        return MultivariateNormal(mean_x, covar_x)  
    

class SHFDeepGP(DeepGP):
    def __init__(
        self, 
        dataset: UCIDataset,
        num_layers: int | None = None, 
        jitter_val: float | None = None, 
        optimize_nu: bool = OPTIMIZE_NU, 
    ) -> None:

        super().__init__()
        self.space = Hypersphere(dataset.dimension)
        self.layers = torch.nn.ModuleList(
            [
                SHFDeepGPLayer(
                    d = dataset.dimension,
                    hidden=True,
                    jitter_val=jitter_val,
                    optimize_nu=optimize_nu,
                    output_dims=dataset.dimension + 1, # Embedding dimension of S^d is d + 1
                ) for _ in range(num_layers - 1)
            ] + 
            [
                SHFDeepGPLayer(
                    d = dataset.dimension,
                    hidden=False,
                    jitter_val=jitter_val,
                    optimize_nu=optimize_nu,
                    output_dims=dataset.num_outputs, # For UCI datasets output is always 1-dimensional
                )
            ]
        )
        self.likelihood = MultitaskGaussianLikelihood(num_tasks=dataset.num_outputs)
        self.likelihood.noise = OUTPUT_LAYER_VARIANCE

    def forward(self, x: Tensor, are_samples: bool = False) -> Tensor:
        for layer in self.layers[:-1]:
            ambient = sample_elementwise(layer(x, are_samples=are_samples))
            tangent = self.space.to_tangent(ambient, x)
            assert ambient.device == tangent.device == x.device, f"All tensors should be on the same device. Got {ambient.device=}, {tangent.device=}, {x.device=}"
            x = self.space.metric.exp(tangent, x)
            are_samples = True
        return self.layers[-1](x, are_samples=are_samples)
