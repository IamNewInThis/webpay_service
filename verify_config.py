#!/usr/bin/env python3
"""
🧪 Script de verificación de configuración multi-cliente
=========================================================
Este script verifica que la configuración de clientes se cargue correctamente.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_client_config():
    """Prueba la carga de configuración de clientes"""
    print("🧪 Probando carga de configuración de clientes...\n")
    
    try:
        from src.client_config import client_loader
        
        print(f"📂 Cargando configuración desde clients.yaml...")
        
        # Obtener clientes activos
        active_clients = client_loader.get_active_clients()
        
        print(f"\n✅ Configuración cargada correctamente!")
        print(f"📊 Total de clientes activos: {len(active_clients)}\n")
        
        if not active_clients:
            print("⚠️  No hay clientes activos configurados")
            print("💡 Edita clients.yaml y agrega al menos un cliente con enabled: true")
            return False
        
        # Mostrar información de cada cliente
        for i, client in enumerate(active_clients, 1):
            print(f"{'='*60}")
            print(f"Cliente #{i}: {client.client_name}")
            print(f"{'='*60}")
            print(f"  🆔 ID: {client.client_id}")
            print(f"  🌐 Dominios permitidos:")
            for origin in client.allowed_origins:
                print(f"     - {origin}")
            print(f"  🏪 Odoo URL: {client.odoo.url}")
            print(f"  📊 Base de datos: {client.odoo.database}")
            print(f"  👤 Usuario: {client.odoo.username}")
            print(f"  💳 Webpay Provider ID: {client.webpay.provider_id}")
            print(f"  💳 Webpay Payment Method ID: {client.webpay.payment_method_id}")
            print(f"  ✅ Estado: {'Activo' if client.enabled else 'Inactivo'}")
            print()
        
        # Probar identificación por origen
        print(f"{'='*60}")
        print("🔍 Probando identificación de cliente por origen...")
        print(f"{'='*60}\n")
        
        for client in active_clients:
            if client.allowed_origins:
                test_origin = client.allowed_origins[0]
                identified_client = client_loader.get_client_by_origin(test_origin)
                
                if identified_client:
                    print(f"✅ Origen: {test_origin}")
                    print(f"   → Identificado como: {identified_client.client_name}")
                else:
                    print(f"❌ Origen: {test_origin}")
                    print(f"   → No se pudo identificar cliente")
                print()
        
        return True
        
    except FileNotFoundError:
        print("❌ Error: Archivo clients.yaml no encontrado")
        print("💡 Crea el archivo desde la plantilla:")
        print("   cp clients.yaml.example clients.yaml")
        return False
        
    except Exception as e:
        print(f"❌ Error cargando configuración: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_imports():
    """Verifica que todos los imports funcionen"""
    print("🧪 Verificando imports del proyecto...\n")
    
    try:
        print("  Importando src.client_config... ", end="")
        from src.client_config import ClientConfig, ClientConfigLoader
        print("✅")
        
        print("  Importando src.config... ", end="")
        from src.config import settings
        print("✅")
        
        print("  Importando src.security... ", end="")
        from src.security import verify_origin
        print("✅")
        
        print("  Importando src.services.odoo_sales... ", end="")
        from src.services.odoo_sales import OdooSalesService
        print("✅")
        
        print("\n✅ Todos los imports funcionan correctamente!\n")
        return True
        
    except ImportError as e:
        print(f"❌\n\nError de importación: {str(e)}")
        print("\n💡 Asegúrate de instalar todas las dependencias:")
        print("   pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌\n\nError inesperado: {str(e)}")
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🏢 WEBPAY SERVICE - VERIFICACIÓN DE CONFIGURACIÓN")
    print("="*60 + "\n")
    
    # Verificar imports primero
    if not test_imports():
        sys.exit(1)
    
    # Luego verificar configuración
    if not test_client_config():
        sys.exit(1)
    
    print("="*60)
    print("🎉 ¡Todas las verificaciones pasaron exitosamente!")
    print("="*60)
    print("\n💡 Siguiente paso: Iniciar el servidor")
    print("   uvicorn src.main:app --reload --host 0.0.0.0 --port 8000\n")
