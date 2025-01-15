import os

def extract_images(
        page_number, 
        page, 
        pdf_path
    ) -> dict:
    """
    Extracts images from a given PDF page:
    - Identifies image bounding boxes
    - Crops and saves images as PNG files in a specified output directory
    - Returns a dictionary that maps a textual key to ((x0, y0, x1, y1), image_path)
    
    This allows referencing images by their coordinates and file paths.
    """
    # Align working directory with the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Generate a base file name for saved images from the PDF file name
    file_name = '_'.join(os.path.splitext(os.path.basename(pdf_path))[0].split()[1:])
    image_dict = {}
    images = page.images

    for j, image in enumerate(images, start=1):
        # Extract the coordinates of the image
        x0, y0, x1, y1 = image['x0'], image['top'], image['x1'], image['bottom']
        # Convert that PDF region to a PIL image at 300 DPI
        img = page.within_bbox((x0, y0, x1, y1)).to_image(resolution=300)
        
        # Create an output directory for images if it doesn't exist
        output_dir = os.path.join(script_dir, "data", "out_images")
        os.makedirs(output_dir, exist_ok=True)
        
        # Save the extracted image
        out_path_img = os.path.join(output_dir, f"{file_name}_image_page{page_number}_n{j}.png")
        img.save(out_path_img)
        
        # Store coordinates and image path
        image_dict[f'Page {page_number} image {j}'] = ((x0, y0, x1, y1), out_path_img)

    return image_dict

def _extract_images_from_page(
        page_number, 
        page, 
        pdf_path, 
        elements
    ):
    """
    Helper function to integrate image extraction into the workflow.
    Extracts images for the given page and appends them as 'image' elements to 'elements'.
    """
    images_per_page = extract_images(page_number, page, pdf_path)
    for key in images_per_page.keys():
        elements.append({
            'type': 'image',
            'content': key,
            'top': images_per_page[key][0][1],
            'img_path': images_per_page[key][1]
        })
    return images_per_page, elements
