from PIL import Image

# Load the original image
img = Image.open(r'c:\Users\Buenaflor\redmovierec_project\moviehub\static\images\auth-bg.jpg')

# Upscale to 1920x1080 (common desktop resolution) with high-quality resampling
img_resized = img.resize((1920, 1080), Image.Resampling.LANCZOS)

# Save with high quality
img_resized.save(
    r'c:\Users\Buenaflor\redmovierec_project\moviehub\static\images\auth-bg.jpg',
    quality=90,
    optimize=True
)

print("✓ Image upscaled to 1920x1080 and saved with quality=90")
