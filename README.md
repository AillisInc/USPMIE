# Officical implementation of the paper: **A Practical Framework for Unsupervised Structure Preservation Medical Image Enhancement**
**Authors**: Quan Huu Cap, Atsushi Fukuda, Hitoshi Iyatomi  
**Paper**: https://arxiv.org/abs/2304.01864

**Abstract**: Medical images are extremely valuable for supporting medical diagnoses. However, in practice, low-quality (LQ) medical images, such as images that are hazy/blurry, have uneven illumination, or are out of focus, among others, are often obtained during data acquisition. This leads to difficulties in the screening and diagnosis of medical diseases. Several generative adversarial networks (GAN)-based image enhancement methods have been proposed and have shown promising results. However, there is a quality-originality trade-off among these methods in the sense that they produce visually pleasing results but lose the ability to preserve originality, especially the structural inputs. Moreover, to our knowledge, there is no objective metric in evaluating the structure preservation of medical image enhancement methods in unsupervised settings due to the unavailability of paired ground-truth data. In this study, we propose a framework for practical unsupervised medical image enhancement that includes (1) a nonreference objective evaluation of structure preservation for medical image enhancement tasks called Laplacian structural similarity index measure (LaSSIM), which is based on SSIM and the Laplacian pyramid, and (2) a novel unsupervised GAN-based method called Laplacian medical image enhancement (LaMEGAN) to support the improvement of both originality and quality from LQ images. The LaSSIM metric does not require clean reference images and has been shown to be superior to SSIM in capturing image structural changes under image degradations, such as strong blurring on different datasets. The experiments demonstrated that our LaMEGAN achieves a satisfactory balance between quality and originality, with robust structure preservation performance while generating compelling visual results with very high image quality scores.

## The Laplacian structural similarity index measurement – LaSSIM
For more experimental results of LaSSIM, please refer to this [page](LaSSIM).  
The code of LaSSIM be released upon acceptance.

## The unsupervised medical image enhancement method – LaMEGAN
For the results of LaMEGAN, please refer to this [page](LaMEGAN).  
The code for LaMEGAN will be released upon acceptance.  

## Citation
```
@article{cap2025uspmie,
    title = A Practical Framework for Unsupervised Structure Preservation Medical Image Enhancement},
    author = {Quan Huu Cap and Atsushi Fukuda and and Hitoshi Iyatomi},
    journal = {Biomedical Signal Processing and Control},
    year = {2025},
    doi = {10.1016/j.bspc.2024.106918},
    url = {https://arxiv.org/abs/2304.01864}
}
```

## Acknowledgments
Our code is inspired by [pytorch-CycleGAN](https://github.com/junyanz/pytorch-CycleGAN-and-pix2pix).