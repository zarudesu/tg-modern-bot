 workflow не активирован")
        print("  • Ошибки в настройке Google Sheets API")
        print("  • Проблемы с аутентификацией")
        print("  • Сетевые проблемы")
        
    print("\n🔧 СЛЕДУЮЩИЕ ШАГИ:")
    print("1. Проверьте n8n workflow активирован")
    print("2. Проверьте Google Sheets ID в настройках")
    print("3. Проверьте Service Account права доступа")
    print("4. Посмотрите логи n8n для детальной диагностики")

if __name__ == "__main__":
    asyncio.run(main())
