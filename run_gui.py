"""图形界面启动入口。"""
from app.interfaces.gui.main_window import ShortDramaSimpleGUI


if __name__ == "__main__":
    app = ShortDramaSimpleGUI()
    app.mainloop()
