import axios from 'axios';

async function testUrl() {
  const url = 'https://codebydante-brodyfilestreambot.hf.space/stream/7361?hash=1deaf9';
  try {
    const response = await axios({
      url,
      method: 'GET',
      responseType: 'arraybuffer',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://google.com'
      }
    });

    console.log('Headers:', response.headers);
    console.log('Content-Type:', response.headers['content-type']);
  } catch (err) {
    console.error(err);
  }
}

testUrl();
