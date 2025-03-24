import torch
from torchvision import transforms
import itertools
from util.image_pool import ImagePool
from .base_model import BaseModel
from . import networks

from kornia.geometry.transform import pyramid

# for running on GPU
class LaplacianPyramid:
    def __init__(self, max_level=5):
		# choose the max_level depends on the image sizes
        self.max_level = max_level

    def extract(self, tensor_img, level=3):
        self.lower = transforms.Grayscale()(tensor_img)
        self.gauss_pyr = [self.lower]

        # get the Gaussian Pyramid
        for i in range(self.max_level):
            self.lower = pyramid.pyrdown(self.lower)

            self.gauss_pyr.append(self.lower)

        # last level of Gaussian remains same in Laplacian
        laplacian_top = self.gauss_pyr[-1]

        # create a Laplacian Pyramid
        self.laplacian_pyr = [laplacian_top]

        for i in range(self.max_level,0,-1):
            gaussian_expanded = pyramid.pyrup(self.gauss_pyr[i])

            laplacian = torch.subtract(self.gauss_pyr[i-1], gaussian_expanded)

            self.laplacian_pyr.append(laplacian)
        
        laplacian = self.laplacian_pyr[self.max_level - level]

        return laplacian


class LaMEGANModel(BaseModel):
	"""This class implements the (Laplacian medical image enhancement) LaMEGAN model.
	LaMEGAN paper: https://www.sciencedirect.com/science/article/abs/pii/S1746809424009765
	"""
	@staticmethod
	def modify_commandline_options(parser, is_train=True):
		"""Add new dataset-specific options, and rewrite default values for existing options.

		Parameters:
			parser          -- original option parser
			is_train (bool) -- whether training phase or test phase. You can use this flag to add training-specific or test-specific options.

		Returns:
			the modified parser.
		"""
		parser.set_defaults(no_dropout=True)  # not use dropout by default
		if is_train:
			parser.add_argument('--lambda_A', type=float, default=10.0, help='weight for cycle loss (A -> B -> A)')
			parser.add_argument('--lambda_B', type=float, default=10.0, help='weight for cycle loss (B -> A -> B)')

			parser.add_argument('--lambda_identity', type=float, default=0.0, help='use identity mapping. \
				Setting lambda_identity other than 0 has an effect of scaling the weight of the identity mapping loss. \
				For example, if the weight of the identity loss should be 10 times smaller than the weight of the reconstruction loss, \
				please set lambda_identity = 0.1')

			parser.add_argument('--lambda_percep', type=float, default=0.25, help='perceptual loss coefficient')
			parser.add_argument('--fea_block', type=str, default='block_2', help='which feature block from VGG19 to extract')
			parser.add_argument('--pyramid_level', type=int, default=3, help='pyramid level to extract')

		return parser

	def __init__(self, opt):
		"""Initialize the class.

		Parameters:
			opt (Option class)-- stores all the experiment flags; needs to be a subclass of BaseOptions
		"""
		BaseModel.__init__(self, opt)
		# specify the training losses you want to print out. The training/test scripts will call <BaseModel.get_current_losses>
		self.loss_names = ['D_A', 'G_A', 'cycle_A', 'idt_A', 'percep_A', 
		'D_B', 'G_B', 'cycle_B', 'idt_B', 'percep_B']
		# specify the images you want to save/display. The training/test scripts will call <BaseModel.get_current_visuals>
		visual_names_A = ['real_A', 'fake_B', 'rec_A']
		visual_names_B = ['real_B', 'fake_A', 'rec_B']
		if self.isTrain and self.opt.lambda_identity > 0.0:  # if identity loss is used, we also visualize idt_B=G_A(B) ad idt_A=G_A(B)
			visual_names_A.append('idt_B')
			visual_names_B.append('idt_A')

		self.visual_names = visual_names_A + visual_names_B  # combine visualizations for A and B
		# specify the models you want to save to the disk. The training/test scripts will call <BaseModel.save_networks> and <BaseModel.load_networks>.
		if self.isTrain:
			self.model_names = ['G_A', 'G_B', 'D_A', 'D_B']
		else:  # during test time, only load Gs
			self.model_names = ['G_A', 'G_B']

		# define networks (both Generators and discriminators)
		# The naming is different from those used in the paper.
		# Code (vs. paper): G_A (G), G_B (F), D_A (D_Y), D_B (D_X)
		self.netG_A = networks.define_G(opt.input_nc, opt.output_nc, opt.ngf, opt.netG, opt.norm,
										not opt.no_dropout, opt.init_type, opt.init_gain, self.gpu_ids)
		self.netG_B = networks.define_G(opt.output_nc, opt.input_nc, opt.ngf, opt.netG, opt.norm,
										not opt.no_dropout, opt.init_type, opt.init_gain, self.gpu_ids)
		
		######################################################

		if self.isTrain:  # define discriminators
			self.netD_A = networks.define_D(opt.output_nc, opt.ndf, opt.netD,
											opt.n_layers_D, opt.norm, opt.init_type, opt.init_gain, self.gpu_ids)
			self.netD_B = networks.define_D(opt.input_nc, opt.ndf, opt.netD,
											opt.n_layers_D, opt.norm, opt.init_type, opt.init_gain, self.gpu_ids)
			
			# load the pre-trained VGG
			######################################################
			# extract the feature of the pretrained VGG19
			fea_layer = 9
			if(opt.fea_block == 'block_1'):
				fea_layer = 4
			elif(opt.fea_block == 'block_2'):
				fea_layer = 9
			elif(opt.fea_block == 'block_3'):
				fea_layer = 18
			elif(opt.fea_block == 'block_4'):
				fea_layer = 27

			self.netF = networks.define_F(feature_layer=fea_layer)

			self.laplacPyr = LaplacianPyramid()
			self.extract_level = opt.pyramid_level

		if self.isTrain:
			if opt.lambda_identity > 0.0:  # only works when input and output images have the same number of channels
				assert(opt.input_nc == opt.output_nc)
			self.fake_A_pool = ImagePool(opt.pool_size)  # create image buffer to store previously generated images
			self.fake_B_pool = ImagePool(opt.pool_size)  # create image buffer to store previously generated images
			# define loss functions
			self.criterionGAN = networks.GANLoss(opt.gan_mode).to(self.device)  # define GAN loss.
			self.criterionCycle = torch.nn.L1Loss()

			self.criterionPerceptual = torch.nn.L1Loss()
			self.criterionCyclePercep = torch.nn.L1Loss()

			self.criterionIdt = torch.nn.L1Loss()
			# initialize optimizers; schedulers will be automatically created by function <BaseModel.setup>.
			self.optimizer_G = torch.optim.Adam(itertools.chain(self.netG_A.parameters(), self.netG_B.parameters()), lr=opt.lr, betas=(opt.beta1, 0.999))
			self.optimizer_D = torch.optim.Adam(itertools.chain(self.netD_A.parameters(), self.netD_B.parameters()), lr=opt.lr, betas=(opt.beta1, 0.999))
			self.optimizers.append(self.optimizer_G)
			self.optimizers.append(self.optimizer_D)


	def set_input(self, input):
		"""Unpack input data from the dataloader and perform necessary pre-processing steps.

		Parameters:
			input (dict): include the data itself and its metadata information.

		The option 'direction' can be used to swap domain A and domain B.
		"""
		AtoB = self.opt.direction == 'AtoB'
		self.real_A = input['A' if AtoB else 'B'].to(self.device)
		self.real_B = input['B' if AtoB else 'A'].to(self.device)
		self.image_paths = input['A_paths' if AtoB else 'B_paths']


	def forward(self):
		"""Run forward pass; called by both functions <optimize_parameters> and <test>."""
		# Fore real_A input
		self.fake_B = self.netG_A(self.real_A)  # G_A(A)
		self.rec_A = self.netG_B(self.fake_B)   # G_B(G_A(A))

		# For real_B input
		self.fake_A = self.netG_B(self.real_B)  # G_B(B)
		self.rec_B = self.netG_A(self.fake_A)   # G_A(G_B(B))

		if(self.isTrain):
			# perceptual loss in extracted laplac pyramid
			self.new_real_A = self.laplacPyr.extract(self.real_A, level=self.extract_level)
			self.new_fake_B = self.laplacPyr.extract(self.fake_B, level=self.extract_level)

			self.new_real_B = self.laplacPyr.extract(self.real_B, level=self.extract_level)
			self.new_fake_A = self.laplacPyr.extract(self.fake_A, level=self.extract_level)

			# convert [1, 1, H, W] --> [1, 3, H, W]
			self.new_real_A = self.new_real_A.tile((1,3,1,1))
			self.new_real_B = self.new_real_B.tile((1,3,1,1))

			self.new_fake_A = self.new_fake_A.tile((1,3,1,1))
			self.new_fake_B = self.new_fake_B.tile((1,3,1,1))

			# extract feature in laplac pyramid
			self.fea_real_A = self.netF(self.new_real_A)
			self.fea_fake_B = self.netF(self.new_fake_B)

			self.fea_fake_A = self.netF(self.new_fake_A)
			self.fea_real_B = self.netF(self.new_real_B)


	def backward_D_basic(self, netD, real, fake):
		"""Calculate GAN loss for the discriminator

		Parameters:
			netD (network)      -- the discriminator D
			real (tensor array) -- real images
			fake (tensor array) -- images generated by a generator

		Return the discriminator loss.
		We also call loss_D.backward() to calculate the gradients.
		"""
		# Real
		pred_real = netD(real)
		loss_D_real = self.criterionGAN(pred_real, True)
		# Fake
		pred_fake = netD(fake.detach())
		loss_D_fake = self.criterionGAN(pred_fake, False)
		# Combined loss and calculate gradients
		loss_D = (loss_D_real + loss_D_fake) * 0.5
		loss_D.backward()
		return loss_D

	def backward_D_A(self):
		"""Calculate GAN loss for discriminator D_A"""
		fake_B = self.fake_B_pool.query(self.fake_B)
		self.loss_D_A = self.backward_D_basic(self.netD_A, self.real_B, fake_B)

	def backward_D_B(self):
		"""Calculate GAN loss for discriminator D_B"""
		fake_A = self.fake_A_pool.query(self.fake_A)
		self.loss_D_B = self.backward_D_basic(self.netD_B, self.real_A, fake_A)

	def backward_G(self):
		"""Calculate the loss for generators G_A and G_B"""
		lambda_idt = self.opt.lambda_identity
		lambda_A = self.opt.lambda_A
		lambda_percep_A = self.opt.lambda_percep

		lambda_B = self.opt.lambda_B
		lambda_percep_B = self.opt.lambda_percep

		# Identity loss
		if lambda_idt > 0:
			# G_A should be identity if real_B is fed: ||G_A(B) - B||
			self.idt_A = self.netG_A(self.real_B)
			self.loss_idt_A = self.criterionIdt(self.idt_A, self.real_B) * lambda_B * lambda_idt
			# G_B should be identity if real_A is fed: ||G_B(A) - A||
			self.idt_B = self.netG_B(self.real_A)
			self.loss_idt_B = self.criterionIdt(self.idt_B, self.real_A) * lambda_A * lambda_idt
		else:
			self.loss_idt_A = 0.0
			self.loss_idt_B = 0.0

		# GAN loss D_A(G_A(A))
		self.loss_G_A = self.criterionGAN(self.netD_A(self.fake_B), True)
		# GAN loss D_B(G_B(B))
		self.loss_G_B = self.criterionGAN(self.netD_B(self.fake_A), True)

		# Forward cycle loss || G_B(G_A(A)) - A||
		self.loss_cycle_A = self.criterionCycle(self.rec_A, self.real_A) * lambda_A
		# Backward cycle loss || G_A(G_B(B)) - B||
		self.loss_cycle_B = self.criterionCycle(self.rec_B, self.real_B) * lambda_B

		# Perceptual loss
		self.loss_percep_A = self.criterionPerceptual(self.fea_real_A, self.fea_fake_B) * lambda_percep_A
		self.loss_percep_B = self.criterionPerceptual(self.fea_real_B, self.fea_fake_A) * lambda_percep_B			

		# combined loss and calculate gradients
		self.loss_G = self.loss_G_A + self.loss_G_B + self.loss_cycle_A \
					+ self.loss_cycle_B + self.loss_idt_A + self.loss_idt_B \
					+ self.loss_percep_A + self.loss_percep_B

		self.loss_G.backward()

	def optimize_parameters(self):
		"""Calculate losses, gradients, and update network weights; called in every training iteration"""
		# forward
		self.forward()      # compute fake images and reconstruction images.
		# G_A and G_B
		self.set_requires_grad([self.netD_A, self.netD_B], False)  # Ds require no gradients when optimizing Gs
		self.optimizer_G.zero_grad()  # set G_A and G_B's gradients to zero
		self.backward_G()             # calculate gradients for G_A and G_B
		self.optimizer_G.step()       # update G_A and G_B's weights
		# D_A and D_B
		self.set_requires_grad([self.netD_A, self.netD_B], True)
		self.optimizer_D.zero_grad()   # set D_A and D_B's gradients to zero
		self.backward_D_A()      # calculate gradients for D_A
		self.backward_D_B()      # calculate graidents for D_B
		self.optimizer_D.step()  # update D_A and D_B's weights