
const IMGBB_API_KEY = '7355790b4703d6853d1be61aab165411';

export const uploadImageToImgBB = async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append('image', file);

    try {
        const response = await fetch(`https://api.imgbb.com/1/upload?key=${IMGBB_API_KEY}`, {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();

        if (data.success) {
            return data.data.url;
        } else {
            throw new Error(data.error?.message || 'Error uploading image');
        }
    } catch (error) {
        console.error('Error uploading to ImgBB:', error);
        throw error;
    }
};
