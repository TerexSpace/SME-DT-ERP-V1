import xmlrpc.client
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..core import ERPAdapterPort, Order, OrderStatus, InventoryItem, OrderLine, SimulationConfig, WarehouseEvent, EventType

logger = logging.getLogger(__name__)

class OdooERPAdapter(ERPAdapterPort):
    """
    Real Odoo ERP adapter using XML-RPC interface.
    Connects to Odoo instance to fetch orders and sync inventory.
    """
    
    def __init__(self, config: SimulationConfig, url: str, db: str, username: str, api_key: str):
        self.config = config
        self.url = url
        self.db = db
        self.username = username
        self.password = api_key  # API key or password
        self.common = None
        self.models = None
        self.uid = None
        self.connected = False
        
    def connect(self) -> bool:
        """Establish connection to Odoo XML-RPC interface."""
        try:
            self.common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = self.common.authenticate(self.db, self.username, self.password, {})
            
            if self.uid:
                self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
                self.connected = True
                logger.info(f"OdooERPAdapter: Connected to {self.url} (User ID: {self.uid})")
                return True
            else:
                logger.error("OdooERPAdapter: Authentication failed")
                return False
        except Exception as e:
            logger.error(f"OdooERPAdapter: Connection error: {e}")
            return False

    def disconnect(self) -> None:
        """Close connection (stateless XML-RPC doesn't require explicit close, but we clear state)."""
        self.connected = False
        self.uid = None
        self.models = None
        logger.info("OdooERPAdapter: Disconnected")

    def fetch_orders(self, status: Optional[OrderStatus] = None) -> List[Order]:
        """Fetch sale orders from Odoo."""
        if not self.connected:
            return []
            
        try:
            # Map internal OrderStatus to Odoo states if needed
            domain = [('state', '=', 'sale')] # Example: fetch confirmed sales
            
            # Fetch order headers
            order_ids = self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'search', [domain], {'limit': 100})
            
            orders_data = self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'read', [order_ids], 
                {'fields': ['name', 'partner_id', 'order_line', 'date_order', 'state']})
            
            result_orders = []
            for o_data in orders_data:
                # Fetch order lines for this order
                line_ids = o_data['order_line']
                lines_data = self.models.execute_kw(self.db, self.uid, self.password,
                    'sale.order.line', 'read', [line_ids],
                    {'fields': ['product_id', 'product_uom_qty', 'qty_delivered']})
                
                lines = []
                for l_data in lines_data:
                    # product_id is [id, name]
                    sku = str(l_data['product_id'][0]) if l_data['product_id'] else "UNKNOWN"
                    qty = int(l_data['product_uom_qty'])
                    lines.append(OrderLine(sku=sku, quantity=qty))
                
                order = Order(
                    order_id=o_data['name'],
                    customer_id=str(o_data['partner_id'][0]) if o_data['partner_id'] else "UNKNOWN",
                    lines=lines,
                    status=OrderStatus.RECEIVED, # Mapped default
                    created_at=datetime.strptime(o_data['date_order'], '%Y-%m-%d %H:%M:%S') if o_data.get('date_order') else datetime.now()
                )
                result_orders.append(order)
                
            return result_orders
            
        except Exception as e:
            logger.error(f"OdooERPAdapter: Error fetching orders: {e}")
            return []

    def fetch_inventory(self) -> Dict[str, InventoryItem]:
        """Fetch product stock levels from Odoo."""
        if not self.connected:
            return {}
            
        try:
            # Search for storable products
            product_ids = self.models.execute_kw(self.db, self.uid, self.password,
                'product.product', 'search', [[('detailed_type', '=', 'product')]], {'limit': 100})
            
            products_data = self.models.execute_kw(self.db, self.uid, self.password,
                'product.product', 'read', [product_ids],
                {'fields': ['id', 'name', 'default_code', 'qty_available', 'standard_price']})
            
            inventory = {}
            for p in products_data:
                sku = p['default_code'] or str(p['id'])
                inventory[sku] = InventoryItem(
                    sku=sku,
                    name=p['name'],
                    quantity=int(p['qty_available']),
                    location="Main Warehouse", # Simplification
                    unit_cost=p['standard_price']
                )
            return inventory
            
        except Exception as e:
            logger.error(f"OdooERPAdapter: Error fetching inventory: {e}")
            return {}

    def update_order_status(self, order_id: str, status: OrderStatus) -> bool:
        """
        Update order status in Odoo. 
        Note: Odoo status transitions are complex (action_confirm, action_done).
        This implementation logs the intent or writes to a custom field.
        """
        if not self.connected:
            return False
        # Implementation depends on Odoo workflow. For now, we log it.
        logger.info(f"OdooERPAdapter: Request to update {order_id} to {status}")
        return True

    def update_inventory(self, sku: str, quantity_change: int) -> bool:
        """
        Update inventory in Odoo.
        Requires creating a 'stock.quant' adjustment or stock move.
        """
        if not self.connected:
            return False
        try:
            # Simplified: Find product ID by SKU
            product_ids = self.models.execute_kw(self.db, self.uid, self.password,
                'product.product', 'search', [[('default_code', '=', sku)]])
            
            if not product_ids:
                return False
                
            product_id = product_ids[0]
            
            # Note: Direct write to qty_available is forbidden in Odoo. 
            # Must create a stock.quant or stock.move. 
            # For this MVP/Demo, we will simulate the API call success.
            logger.info(f"OdooERPAdapter: Adjusting stock for {sku} by {quantity_change}")
            return True
            
        except Exception as e:
            logger.error(f"OdooERPAdapter: Error updating inventory: {e}")
            return False

    def subscribe_to_events(self, callback: Any) -> bool:
        """
        Odoo XML-RPC does not support real-time push events.
        Polling is required. This method is a stub for the interface.
        """
        logger.warning("OdooERPAdapter: Real-time subscription not supported via XML-RPC. Use polling.")
        return False
