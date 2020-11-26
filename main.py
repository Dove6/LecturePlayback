import argparse
import os
import re

import fitz
import mpv
import tkinter as tk
import tkinter.messagebox as tkmsgbox


def parse_line(line):
    if line.count('@') != 1:
            raise Exception('Invalid description line format!')
    time = line[:line.find('@')].strip()
    page = int(line[(line.find('@')+1):].strip())
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
        raise Exception('Invalid description line format!')
    time_ms = time_parts['msecs']
    time_ms += time_parts['hours'] * 3600000 + time_parts['mins'] * 60000 + time_parts['secs'] * 1000
    return {'timestamp': time_ms, 'pagename': page}

def parse_description(filename):
    timestamps = []
    with open(filename) as desc:
        for line in desc:
            timestamps.append(parse_line(line))
    return sorted(timestamps, key=(lambda x: x['timestamp']))

def time_to_index(description, ms):
    description = list(filter(lambda x: x['timestamp'] < ms, description))
    if len(description) > 0:
        return (description[-1]['pagename'] - 1)


class Application:
    EXTENSIONS = {
        'audio': sorted([
            'aac',
            'ape',
            'caf',
            'flac',
            'm4a',
            'm4b',
            'm4p',
            'm4r',
            'mka',
            'mp3',
            'mpc',
            'mpp',
            'ogg',
            'opus',
            'ra',
            'ram',
            'shn',
            'wma',
            'wv',
        ]),
        'presentation': sorted([
            'pdf',
        ])
    }

    def __init__(self, width, height, paths):
        if width < 0 or height < 0:
            raise Exception('Negative video dimensions specified!')
        self.width = width
        self.height = height
        assert('audio' in paths.keys() and 'description' in paths.keys() and 'presentation' in paths.keys())
        self.paths = dict(filter(lambda x: x[0] in ['audio', 'description', 'presentation'], paths.items()))
        self.description = parse_description(paths['description'])
        self.pdf = fitz.open(paths['presentation'])
        self.page_num = None
        self.player = mpv.MPV()
        self.player.play(paths['audio'])
        self.player.video = 'no'
        self.player.pause = True
        self.player.keep_open = True
        self.tkids = {}
        self.tkroot = tk.Tk()
        # self.tkroot.geometry(f'{width}x{height}')
        self.tkroot.title(paths['presentation'])
        self.tkroot.protocol("WM_DELETE_WINDOW", self.quit)
        self.tkroot.bind('<Key>', self.key_callback)
        self.tkroot.bind('<ButtonRelease-1>', self.left_release_callback)
        self.tkcanvas = tk.Canvas(self.tkroot, width=width, height=height, borderwidth=0, highlightthickness=0)
        self.tkcanvas.pack()
        self.tkids['slide'] = self.tkcanvas.create_image(0, 0,
            anchor=tk.NW)
        self.tkids['osdbkg'] = self.tkcanvas.create_rectangle(0, height - 24, width, height,
            fill='black', state='hidden', tags='osd')
        self.tkids['playicon'] = self.tkcanvas.create_polygon([3, height - 22, 21, height - 12, 3, height - 2],
            fill='white', state='hidden', tags=['osd', 'play'])
        self.tkids['pauseicon1'] = self.tkcanvas.create_rectangle(2, height - 22, 9, height - 2,
            fill='white', state='hidden', tags=['osd', 'pause'])
        self.tkids['pauseicon2'] = self.tkcanvas.create_rectangle(14, height - 22, 21, height - 2,
            fill='white', state='hidden', tags=['osd', 'pause'])
        self.tkids['progress'] = self.tkcanvas.create_rectangle(26, height - 22, width - 28, height - 2,
            fill='white', state='hidden', tags='osd')
        self.tkroot.withdraw()
        self.tkimage = None
        self._osd_visible = False
        @self.player.property_observer('time-pos')
        def slide_changer(_name, value):
            if value is not None:
                self.update_page(time_to_index(self.description, value * 1000))
        @self.player.property_observer('percent-pos')
        def progress_changer(_name, value):
            if value is not None:
                self.tkcanvas.coords(self.tkids['progress'],
                        26, height - 22, 26 + (width - 28) * value / 100, height - 2)
    
    def __del__(self):
        if hasattr(self, 'player'):
            self.player.terminate()
        if hasattr(self, 'tkroot'):
            self.tkroot.destroy()

    @property
    def player_paused(self):
        return self.player.pause

    @player_paused.setter
    def player_paused(self, value):
        self.player.pause = bool(value)
        if self.player.pause and self.osd_visible:
            self.tkcanvas.itemconfig('pause', state='hidden')
            self.tkcanvas.itemconfig('play', state='normal')
        elif self.osd_visible:
            self.tkcanvas.itemconfig('pause', state='normal')
            self.tkcanvas.itemconfig('play', state='hidden')

    @property
    def osd_visible(self):
        return self._osd_visible

    @osd_visible.setter
    def osd_visible(self, value):
        self._osd_visible = bool(value)
        if self._osd_visible:
            self.tkcanvas.itemconfig('osd', state='normal')
            if self.player.pause:
                self.tkcanvas.itemconfig('pause', state='hidden')
            else:
                self.tkcanvas.itemconfig('play', state='hidden')
        else:
            self.tkcanvas.itemconfig('osd', state='hidden')

    def left_release_callback(self, event):
        canvas_x = self.tkcanvas.canvasx(event.x)
        canvas_y = self.tkcanvas.canvasy(event.y)
        # print(event)
        # print((canvas_x, canvas_y))
        if canvas_x < 24 and canvas_y >= self.height - 24 and self.osd_visible:
            self.player_paused = not self.player_paused
        elif 26 <= canvas_x < self.width - 28 and self.height - 22 <= canvas_y < self.height - 2 and self.osd_visible:
            secs = (canvas_x - 26) / (self.width - 28) * self.player.duration
            self.player.seek(secs, reference='absolute')

    def key_callback(self, event):
        if event.keysym in ['Left', 'Right']:
            if self.player.seekable:
                if event.keysym == 'Left':
                    self.player.seek(-5)
                else:
                    self.player.seek(5)
        if event.keysym in ['Up', 'Down']:
            index = self.page_num
            if index is not None:
                if event.keysym == 'Down':
                    self.update_page(index - 1)
                else:
                    self.update_page(index + 1)
            else:
                self.update_page(0)
        elif event.keysym == 'o':
            self.osd_visible = not self.osd_visible
        elif event.keysym in ['p', 'space']:
            self.player_paused = not self.player_paused
        elif event.keysym in ['q', 'Escape']:
            self.quit()

    def update_page(self, index):
        if index is None:
            if self.page_num is not None:
                self.tkcanvas.itemconfig(self.tkids['slide'], image='')
                self.page_num = None
        elif 0 <= index < len(self.pdf):
            if index != self.page_num:
                page = self.pdf[index]
                rect = page.rect
                matrix = fitz.Matrix()
                matrix.a = matrix.d = min(self.width / (rect[2] - rect[0]), self.height / (rect[3] - rect[1]))
                matrix.e = -rect[0]
                matrix.f = -rect[1]
                pix = page.getPixmap(matrix)
                self.tkimage = tk.PhotoImage(data=pix.getImageData('ppm'))
                self.tkcanvas.coords(self.tkids['slide'], (self.width - pix.width) / 2, (self.height - pix.height) / 2)
                self.tkcanvas.itemconfig(self.tkids['slide'], image=self.tkimage)
                self.page_num = index
        else:
            print('Out of range')

    def run(self):
        self.player.pause = False
        self.tkroot.deiconify()
        self.tkroot.mainloop()

    def quit(self):
        self.player.stop()
        self.tkroot.quit()
        self.pdf.close()


if __name__ == '__main__':
    def dialog_error(exception):
        dummy = tk.Tk()
        dummy.withdraw()
        tkmsgbox.showerror(type(exception).__name__, str(exception), parent=dummy)
        dummy.quit()

    def console_error(exception):
        print(f'{type(exception).__name__}: {str(exception)}')

    report_error = console_error

    try:
        parser = argparse.ArgumentParser(description='Mix audio playback and presentation display in real time accordingly to a description file.')
        parser.add_argument('-a', '--audio', help='path of the audio file')
        parser.add_argument('-p', '--presentation', help='path of the presentation file')
        parser.add_argument('--width', default=1280, type=int, help='width of the video output')
        parser.add_argument('--height', default=720, type=int, help='height of the video output')
        parser.add_argument('--no-dialogs', action='store_true', help='use the standard output instead of GUI dialogs for error reporting')
        parser.add_argument('description', help='path of the description file')
        args = parser.parse_args()
        if not args.no_dialogs:
            report_error = dialog_error
        filenames = {
            'audio': args.audio,
            'description': args.description,
            'presentation': args.presentation
        }
        if not os.path.isfile(filenames['description']):
            raise Exception('Invalid description file name!')
        base_name =  os.path.splitext(args.description)[0]
        for file_type in ['audio', 'presentation']:
            if filenames[file_type] is None:
                for extension in Application.EXTENSIONS[file_type]:
                    filenames[file_type] = f'{base_name}.{extension}'
                    if os.path.isfile(filenames[file_type]):
                        break
                else:
                    raise Exception(f'No {file_type} file path provided and no suitable file found!')
        app = Application(args.width, args.height, filenames)
        app.run()
        print('Exited gracefully')
    except Exception as e:
        report_error(e)
