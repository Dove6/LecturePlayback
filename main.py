import re
import fitz
import mpv
import tkinter as tk

def parse_line(line):
    if line.count('@') != 1:
            raise Exception()
    time = line[:line.find('@')].strip()
    page = line[(line.find('@')+1):].strip()

    time_parts = {'hours': 0, 'mins': 0, 'secs': 0, 'msecs': 0}
    if (match := re.fullmatch(r'(\d+):(\d{2}):(\d{2})(\.(\d{1,3}))?', time)) is not None:
        time_parts['hours'] = int(match.group(1))
        time_parts['mins'] = int(match.group(2))
        time_parts['secs'] = int(match.group(3))
        if match.group(4) is not None:
            time_parts['msecs'] = int((match.group(5) + '00')[:3])
    elif (match := re.fullmatch(r'(\d{2}):(\d{2})(\.(\d{1,3}))?', time)) is not None:
        time_parts['mins'] = int(match.group(1))
        time_parts['secs'] = int(match.group(2))
        if match.group(4) is not None:
            time_parts['msecs'] = int((match.group(4) + '00')[:3])
    elif (match := re.fullmatch(r'(\d{2})(\.(\d{1,3}))?', time)) is not None:
        time_parts['secs'] = int(match.group(1))
        if match.group(4) is not None:
            time_parts['msecs'] = int((match.group(3) + '00')[:3])
    else:
        raise Exception()
    time_ms = time_parts['msecs']
    time_ms += time_parts['hours'] * 3600000 + time_parts['mins'] * 60000 + time_parts['secs'] * 1000
    return {'timestamp': time_ms, 'pagename': page}

def parse_description(filename):
    timestamps = []
    with open(filename) as desc:
        for line in desc:
            timestamps.append(parse_line(line))
    return sorted(timestamps, key=(lambda x: x['timestamp']))


class Application:
    def __init__(self, width, height, paths):
        self.width = width
        self.height = height
        assert('audio' in paths.keys() and 'description' in paths.keys() and 'pdf' in paths.keys())
        self.paths = dict(filter(lambda x: x[0] in ['audio', 'description', 'pdf'], paths.items()))
        self.description = parse_description(paths['description'])
        self.pdf = fitz.open(paths['pdf'])
        self.player = mpv.MPV()
        self.player.play(paths['audio'])
        self.player.video = 'no'
        self.player.pause = True
        self.player.keep_open = True
        # @self.player.property_observer('time-pos')
        # def fun(_name, value)
        self.tkroot = tk.Tk()
        self.tkroot.title(paths['pdf'])
        self.tkroot.bind('<Key>', self.key_callback)
        self.tkcanvas = tk.Canvas(self.tkroot, width=width, height=height)
        self.tkcanvas.pack()
        self.tkroot.withdraw()
        self.tkimage = None
        self.page_num = None
    
    def key_callback(self, event):
        if event.keysym in ['Left', 'Right']:
            index = self.page_num
            if index is not None:
                if event.keysym == 'Left':
                    self.update_page(index - 1)
                else:
                    self.update_page(index + 1)
            else:
                self.update_page(0)
        elif event.keysym in ['q', 'Escape']:
            self.quit()

    def update_page(self, index):
        # print(index)
        if 0 <= index < len(self.pdf):
            self.tkcanvas.delete('slide')
            page = self.pdf[index]
            rect = page.rect
            matrix = fitz.Matrix()
            matrix.a = matrix.d = min(self.width / (rect[2] - rect[0]), self.height / (rect[3] - rect[1]))
            matrix.e = -rect[0]
            matrix.f = -rect[1]
            pix = page.getPixmap(matrix)
            self.tkimage = tk.PhotoImage(data=pix.getImageData('ppm'))
            self.tkcanvas.create_image((self.width - pix.width) / 2, (self.height - pix.height) / 2,
                anchor=tk.NW, image=self.tkimage, tags='slide')
            self.page_num = index
        else:
            print('Out of range')

    def run(self):
        self.player.pause = False
        self.tkroot.deiconify()
        self.tkroot.mainloop()

    def quit(self):
        self.tkroot.destroy()
        self.player.terminate()
        self.pdf.close()


if __name__ == '__main__':
    app = Application(1280, 720, {
        'audio': 'example/example.mp3',
        'description': 'example/example.txt',
        'pdf': 'example/example.pdf'
    })
    app.run()
    print('Exited gracefully')
