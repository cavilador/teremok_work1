# coding: utf-8
import sqlite3
import sys
import os

def cleanup_database():
    """Интерактивная очистка базы данных через консоль"""
    
    if not os.path.exists('shifts.db'):
        print("❌ Файл базы данных 'shifts.db' не найден!")
        return
    
    conn = sqlite3.connect('shifts.db')
    cursor = conn.cursor()
    
    print("=" * 50)
    print("ОЧИСТКА БАЗЫ ДАННЫХ БОТА")
    print("=" * 50)
    
    # Показываем статистику
    cursor.execute('SELECT COUNT(*) FROM pending_requests')
    pending = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM approved_shifts')
    approved = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM sent_actions')
    actions = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM user_messages')
    messages = cursor.fetchone()[0]
    
    print(f"\n📊 Текущая статистика:")
    print(f"   📝 Ожидающие заявки: {pending}")
    print(f"   ✅ Одобренные смены: {approved}")
    print(f"   🔄 Выполненные действия: {actions}")
    print(f"   💬 Сообщения пользователей: {messages}")
    
    print("\n🧹 Варианты очистки:")
    print("   1. Очистить только ожидающие заявки")
    print("   2. Удалить смены старше 30 дней")
    print("   3. Полная очистка базы данных")
    print("   4. Создать резервную копию")
    print("   5. Экспорт в CSV")
    print("   6. Выход")
    
    try:
        choice = input("\nВыберите действие (1-6): ").strip()
        
        if choice == '1':
            confirm = input(f"Удалить {pending} ожидающих заявок? (да/НЕТ): ").lower()
            if confirm == 'да':
                cursor.execute('DELETE FROM pending_requests')
                print(f"✅ Удалено {cursor.rowcount} заявок")
                conn.commit()
        
        elif choice == '2':
            cursor.execute('''
                SELECT COUNT(*) FROM approved_shifts 
                WHERE date(approved_at) < date('now', '-30 days')
            ''')
            old_count = cursor.fetchone()[0]
            
            if old_count > 0:
                confirm = input(f"Удалить {old_count} старых смен? (да/НЕТ): ").lower()
                if confirm == 'да':
                    cursor.execute('''
                        DELETE FROM approved_shifts 
                        WHERE date(approved_at) < date('now', '-30 days')
                    ''')
                    print(f"✅ Удалено {cursor.rowcount} старых смен")
                    conn.commit()
            else:
                print("📭 Старых смен для удаления не найдено")
        
        elif choice == '3':
            confirm = input("⚠️  ВНИМАНИЕ! Полная очистка удалит ВСЕ данные! (да/НЕТ): ").lower()
            if confirm == 'да':
                tables = ['pending_requests', 'approved_shifts', 'sent_actions', 'user_messages']
                for table in tables:
                    cursor.execute(f'DELETE FROM {table}')
                conn.commit()
                print("✅ База данных полностью очищена!")
        
        elif choice == '4':
            import shutil
            import datetime
            
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f'shifts_backup_{timestamp}.db'
            shutil.copy2('shifts.db', backup_file)
            print(f"✅ Резервная копия создана: {backup_file}")
        
        elif choice == '5':
            import csv
            
            export_dir = 'db_export'
            os.makedirs(export_dir, exist_ok=True)
            
            tables = ['pending_requests', 'approved_shifts', 'sent_actions', 'user_messages']
            
            for table in tables:
                cursor.execute(f'SELECT * FROM {table}')
                rows = cursor.fetchall()
                
                if rows:
                    cursor.execute(f'PRAGMA table_info({table})')
                    columns = [col[1] for col in cursor.fetchall()]
                    
                    filename = os.path.join(export_dir, f'{table}.csv')
                    with open(filename, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(columns)
                        writer.writerows(rows)
                    
                    print(f"   📄 Экспортировано: {filename}")
            
            print(f"✅ Экспорт завершен в папку '{export_dir}'")
        
        elif choice == '6':
            print("👋 Выход...")
        
        else:
            print("❌ Неверный выбор")
        
        # Показываем итоговую статистику
        if choice in ['1', '2', '3']:
            cursor.execute('SELECT COUNT(*) FROM pending_requests')
            pending = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM approved_shifts')
            approved = cursor.fetchone()[0]
            
            print(f"\n📊 Итоговая статистика:")
            print(f"   📝 Ожидающие заявки: {pending}")
            print(f"   ✅ Одобренные смены: {approved}")
    
    except KeyboardInterrupt:
        print("\n\n👋 Выход...")
    finally:
        conn.close()

if __name__ == '__main__':
    cleanup_database()