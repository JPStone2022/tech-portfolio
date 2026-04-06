import csv
import requests
import io
import zipfile
from django.utils import timezone
from .models import CuratedProduct

def automated_product_sync():
    """
    Downloads the Awin ZIP, extracts the CSV in memory, updates prices/links, 
    and flags missing items as out of stock.
    """
    FEED_URL = "https://productdata.awin.com/datafeed/download/apikey/5ecc58276a52c518a40eefa5dfaa5b87/language/en/fid/102133/rid/0/hasEnhancedFeeds/0/columns/aw_deep_link,product_name,aw_product_id,merchant_product_id,merchant_image_url,description,merchant_category,search_price,merchant_name,merchant_id,category_name,category_id,aw_image_url,currency,store_price,delivery_cost,merchant_deep_link,language,last_updated,display_price,data_feed_id,brand_name,colour,specifications,product_short_description,keywords,merchant_product_second_category,rrp_price,merchant_thumb_url,large_image,aw_thumb_url,base_price,Fashion%3Asize,size_stock_amount,dimensions,mpn/format/csv/delimiter/%2C/compression/zip/adultcontent/1/"
    
    print("🤖 Starting automated affiliate sync...")
    
    try:
        # 1. Download the ZIP file
        response = requests.get(FEED_URL, timeout=60)
        response.raise_for_status()
        
        raw_bytes = response.content
        
        # 2. Extract the CSV from the ZIP in memory
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                # Find the first file that ends with .csv
                csv_filename = next((name for name in z.namelist() if name.endswith('.csv')), None)
                if not csv_filename:
                    print("❌ No CSV file found inside the zip archive.")
                    return False
                
                print(f"📦 Found '{csv_filename}' in zip archive. Extracting...")
                csv_content_bytes = z.read(csv_filename)
                
        except zipfile.BadZipFile:
            print("❌ Downloaded file is not a valid zip archive.")
            return False

        # 3. Decode the extracted bytes into a readable string
        try:
            csv_content = csv_content_bytes.decode('utf-8-sig')
        except UnicodeDecodeError:
            # Fallback just in case Awin uses older encoding
            csv_content = csv_content_bytes.decode('latin-1')

        # 4. Parse the CSV data
        csv_file_obj = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file_obj)
        
        active_product_ids = set()
        
        # 5. Process the rows
        for row in reader:
            # Using the v1 mapping from your previous script
            mpid = row.get('aw_product_id') 
            if not mpid:
                continue
                
            active_product_ids.add(mpid)
            
            CuratedProduct.objects.update_or_create(
                merchant_product_id=mpid,
                defaults={
                    'title': row.get('product_name', ''),
                    'description': row.get('description', ''),
                    'merchant': row.get('merchant_name', 'Unknown'),
                    'price': row.get('search_price') or None,
                    'buy_url': row.get('aw_deep_link', ''),
                    'image_url': row.get('merchant_image_url', ''),
                    'is_in_stock': True,
                    'last_synced': timezone.now()
                }
            )
            
        # 6. The "Out of Stock" Sweep
        out_of_stock_sweep = CuratedProduct.objects.exclude(
            merchant_product_id__in=active_product_ids
        ).update(is_in_stock=False)
        
        print(f"✅ Sync complete. {len(active_product_ids)} items updated. {out_of_stock_sweep} items marked Out of Stock.")
        return True

    except Exception as e:
        print(f"❌ Automated sync failed: {e}")
        return False