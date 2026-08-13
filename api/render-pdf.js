export default async function handler(req, res) {
  return res.status(200).json({
    renderer: "NEW VERSION",
    chromium: "@sparticuz/chromium"
  });
}
