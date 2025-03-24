import numpy as np
from skimage import metrics
from skimage.color import rgb2gray
import cv2

# for running on CPU
class LaplacianPyramid:
    def __init__(self, max_level: int=5):
        # choose the max_level depends on the image sizes
        self.max_level = max_level

    def extract(self, img: np.ndarray, level: int=3):
        self.lower = img.copy()

        self.gauss_pyr = [self.lower]

        # get the Gaussian Pyramid
        for i in range(self.max_level):
            self.lower = cv2.pyrDown(self.lower)

            self.gauss_pyr.append(self.lower)

        # last level of Gaussian remains same in Laplacian
        laplacian_top = self.gauss_pyr[-1]

        # create a Laplacian Pyramid
        self.laplacian_pyr = [laplacian_top]

        for i in range(self.max_level,0,-1):
            size = (self.gauss_pyr[i - 1].shape[1], self.gauss_pyr[i - 1].shape[0])
            gaussian_expanded = cv2.pyrUp(self.gauss_pyr[i], dstsize=size)

            laplacian = cv2.subtract(self.gauss_pyr[i-1], gaussian_expanded)

            self.laplacian_pyr.append(laplacian)

        laplacian = self.laplacian_pyr[self.max_level - level]

        return laplacian

def LaSSIM(img_inp: np.ndarray, img_ref: np.ndarray, extract_level: int=3):
    """Implementation of the Laplacian structural similarity index measure (LaSSIM) 
    for measuring structural changes for real-world non-reference medical image enhancement tasks.
    Args:
        img_inp (np.ndarray): input image in RGB
        img_ref (np.ndarray): reference image in RGB
        extract_level (int): Laplacian Pyramid extract level (default: 3).
            Please choose the extract level depends on the image sizes
            Using level 3 for image size [272 x 480] in the paper
    """
    # convert to grayscale
    new_inp = rgb2gray(img_inp)
    new_ref = rgb2gray(img_ref)
    
    # calculating SSIM score in Laplace Pyramid
    laplac_pyr = LaplacianPyramid()

    new_inp = laplac_pyr.extract(new_inp, level=extract_level)
    new_ref = laplac_pyr.extract(new_ref, level=extract_level)
        
    max_value = max(new_inp.max(), new_ref.max())
    min_value = min(new_inp.min(), new_ref.min())

    ssim_val = metrics.structural_similarity(new_inp, new_ref, 
                                             data_range = max_value - min_value)
    
    return ssim_val

def SSIM(img_inp: np.ndarray, img_ref: np.ndarray):
    """Structural similarity index measure (SSIM)
    Args:
        img_inp (np.ndarray): input image in RGB
        img_ref (np.ndarray): reference image in RGB
    """ 
    max_value = max(img_inp.max(), img_ref.max())
    min_value = min(img_inp.min(), img_ref.min())

    ssim_val = metrics.structural_similarity(img_inp, img_ref, 
                                             data_range=max_value - min_value,
                                             channel_axis=2)
    
    return ssim_val

if __name__=="__main__":
    # testing LaSSIM vs SSIM
    import albumentations as A
    
    # elastic level
    alpha = 100
    sigma = 2.5

    blur_limit = 17

    # blur augmentation
    _aug_blur = A.Compose([
        A.Blur(blur_limit=(blur_limit, blur_limit), p=1.0),
    ])

    # elastic + blur augmentation
    _aug_elt_blur = A.Compose([
        A.ElasticTransform(alpha=alpha, sigma=sigma, fill=(255, 255, 255), p=1.0),
        A.Blur(blur_limit=(blur_limit, blur_limit), p=1.0),
    ])

    img_path = "resources/image_original.png"

    # read original image
    img_gt = cv2.imread(img_path, -1)

    # add blur
    img_blur = _aug_blur(image=img_gt)['image']

    # add elastic + blur
    img_elt_blur = _aug_elt_blur(image=img_gt)['image']

    # SSIM in Laplace Pyramid space
    lassim_blur_gt = LaSSIM(img_inp=img_blur, img_ref=img_gt)
    lassim_elt_blur_gt = LaSSIM(img_inp=img_elt_blur, img_ref=img_gt)

    print(f"LaSSIM (blur vs original): {lassim_blur_gt}")
    print(f"LaSSIM (elastic+blur vs original): {lassim_elt_blur_gt}\n")

    # SSIM in pixel space
    ssim_blur_gt = SSIM(img_blur, img_gt)
    ssim_elt_blur_gt = SSIM(img_elt_blur, img_gt)

    print(f"SSIM (blur vs original): {ssim_blur_gt}")
    print(f"SSIM (elastic+blur vs original): {ssim_elt_blur_gt}")