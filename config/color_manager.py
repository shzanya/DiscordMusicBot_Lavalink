class ColorManager:
    """Управление цветами эмодзи в боте"""
    
    # Доступные цвета
    AVAILABLE_COLORS = [
        'OLIVE', 'ORANGE', 'PINK', 'PURPLE', 'RED', 
        'SALMON', 'SILVER', 'TEAL', 'WHITE', 'YELLOW'
    ]
    
    # Текущий активный цвет (по умолчанию)
    _current_color = 'PURPLE'
    
    @classmethod
    def set_color(cls, color: str):
        """Установить активный цвет"""
        color = color.upper()
        if color in cls.AVAILABLE_COLORS:
            cls._current_color = color
            return True
        return False
    
    @classmethod
    def get_current_color(cls):
        """Получить текущий цвет"""
        return cls._current_color
    
    @classmethod
    def get_available_colors(cls):
        """Получить список доступных цветов"""
        return cls.AVAILABLE_COLORS
