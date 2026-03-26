# Copyright 2024 Brett Kosinski <brettk@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import time

from chirp import (
    bitwise,
    chirp_common,
    directory,
    errors,
    memmap,
    util,
)
from chirp.settings import (
    RadioSetting,
    RadioSettingGroup,
    RadioSettingValueBoolean,
    RadioSettingValueInteger,
    RadioSettingValueList,
    RadioSettingValueString,
    RadioSettings,
)

LOG = logging.getLogger(__name__)

MEM_FORMAT = """
#seekto 0x0000;
struct {
  lbcd rxfreq[4];
  lbcd txfreq[4];
  u8 rx_tmode;
  u8 rx_tone;
  u8 tx_tmode;
  u8 tx_tone;
  u8 sp_mute:2,
     descramble:4,
     unknown1:1,
     highpower:1;
  u8 call_id:5,
     unknown2:2,
     busy_lock:1;
  u8 unknown3:7,
     wide:1;
  u8 unknown4;
} vfo;

#seekto 0x0100;
struct {
  lbcd rxfreq[4];
  lbcd txfreq[4];
  u8 rx_tmode;
  u8 rx_tone;
  u8 tx_tmode;
  u8 tx_tone;
  u8 sp_mute:2,
     descramble:4,
     unknown1:1,
     highpower:1;
  u8 call_id:5,
     unknown2:2,
     busy_lock:1;
  u8 unknown3:7,
     wide:1;
  u8 unknown4;
} memory[401];

#seekto 0x1B00;
struct {
  u8 name[6];
} names[401];

#seekto 0x0020;
struct {
  u8 squelch;           // 0x0020: 0-9
  u8 vfo_step;          // 0x0021: 0-8
  u8 pf_top_long;       // 0x0022: 1-13
  u8 beep;              // 0x0023: 0=OFF 1=ON
  u8 battery_save;      // 0x0024: 0=OFF 1=ON
  u8 unknown_25;
  u8 voice;             // 0x0026: 0=OFF 2=ON
  u8 unknown_27;
  u8 tot;               // 0x0028: 0=OFF 1-60 (x15s)
  u8 pf_top_short;      // 0x0029: 1-13
  u8 pf2_long;          // 0x002A: 1-13
  u8 unknown_2b;
  u8 auto_lock;         // 0x002C: 0=OFF 1-6 (x10s)
  u8 work_mode;         // 0x002D: 0=Freq 1=Ch/Freq 2=Ch/Num 3=Ch/Name
  u8 scan_mode;         // 0x002E: 0=CO 1=TO 2=SE
  u8 unknown_2f;
  u8 startup_display;   // 0x0030: 0=Message 1=Voltage
  u8 unknown_31;
  u8 roger;             // 0x0032: 0=OFF 1=BOT 2=EOT 3=BOTH
  u8 unknown_33;
  u8 backlight;         // 0x0034: 0=OFF 1-30 31=ALWAYS
  u8 repeater;          // 0x0035: 0=OFF 1=ON (VFO repeater offset enable)
  ul16 active_channel;  // 0x0036-0x0037: 1-400
  u8 unknown_38[4];     // 0x0038-0x003B
  u8 vox;               // 0x003C: 0=OFF 1-9
  u8 toa;               // 0x003D: 0=OFF 1-10
  u8 unknown_3e;
  u8 sidetone;          // 0x003F: 0=OFF 1=DT-ST 2=ANI-ST 3=DT+ANI
  u8 ptt_id;            // 0x0040: 0=OFF 1=BOT 2=EOT 3=BOTH
  u8 unknown_41[4];
  ul16 priority_channel; // 0x0045-0x0046: 1-400
  u8 id_dly;            // 0x0047: 1-30 (x100ms)
  u8 ring;              // 0x0048: 0=OFF 1-10s
  u8 unknown_49;
  u8 lock_mode;         // 0x004A: 0=KEY 1=KEY+PTT 2=KEY+ENC 3=KEY+ALL
  u8 alert_tone;        // 0x004B: 0=1000Hz 1=1450Hz 2=1750Hz 3=2100Hz
  u8 vox_delay;         // 0x004C: 1-5s
  u8 tone_save;         // 0x004D: 0=RX 1=TX 2=TX+RX
  u8 priority_scan;     // 0x004E: 0=OFF 1=ON
  u8 call_reset;        // 0x004F: 0-60s
  u8 unknown_50[3];     // 0x0050-0x0052
  u8 pf1_short;         // 0x0053: 1-13
  u8 pf1_long;          // 0x0054: 1-13
  u8 pf2_short;         // 0x0055: 1-13
  u8 scan_qt;           // 0x0056: 0=OFF 1=ON
  u8 startup_msg[7];    // 0x0057-0x005D
  u8 unknown_5e[2];
  u8 id_control[4];     // 0x0060-0x0063
  u8 unknown_64[2];
  u8 dtmf_tx_time;      // 0x0066: 0-45 (50+x*10 ms)
  u8 dtmf_interval;     // 0x0067: 0-45 (50+x*10 ms)
  u8 unknown_68;
  u8 be_control;        // 0x0069: 0=OFF 1=ON
  u8 id_edit[4];        // 0x006A-0x006D
  u8 unknown_6e[2];
  u8 timer;             // 0x0070: 0=OFF 1=ON
  u8 rpt_rct;           // 0x0071: 0=OFF 1=ON
} settings;

#seekto 0x2680;
struct {
  u8 map[51];
} favorites;

#seekto 0x2700;
struct {
  u8 id[6];
} callids[20];
"""

TONES = chirp_common.TONES
DTCS_CODES = chirp_common.DTCS_CODES
TMODES = ["", "Tone", "DTCS", "DTCS"]

# Settings list constants
LIST_OFF_1_9 = ["Off"] + [str(i) for i in range(1, 10)]
LIST_TOT = ["Off"] + ["%dS" % (i * 15) for i in range(1, 61)]
LIST_AUTO_LOCK = ["Off"] + ["%dS" % (i * 10) for i in range(1, 7)]
LIST_WORK_MODE = ["Freq", "Ch/Freq", "Ch/Num", "Ch/Name"]
LIST_SCAN_MODE = ["CO", "TO", "SE"]
LIST_STARTUP_DISPLAY = ["Message", "Voltage"]
LIST_ROGER = ["Off", "BOT", "EOT", "Both"]
LIST_BACKLIGHT = ["Off"] + [str(i) for i in range(1, 31)] + ["Always"]
LIST_VOX_DELAY = ["1S", "2S", "3S", "4S", "5S"]
LIST_LOCK_MODE = ["Key", "Key+PTT", "Key+Enc", "Key+All"]
LIST_ALERT_TONE = ["1000Hz", "1450Hz", "1750Hz", "2100Hz"]
LIST_TONE_SAVE = ["RX", "TX", "TX+RX"]
LIST_PF_KEY = ["Scan", "Backlight", "VOX", "TX Power", "Call",
               "Talk-Around", "Flashlight", "Monitor", "Reverse",
               "WorkMode", "Alarm", "SOS", "Favorite"]
LIST_SIDETONE = ["Off", "DT-ST", "ANI-ST", "DT+ANI"]
LIST_PTT_ID = ["Off", "BOT", "EOT", "Both"]
LIST_ID_DLY = ["%dMS" % (i * 100) for i in range(1, 31)]
LIST_RING = ["Off"] + ["%dS" % i for i in range(1, 11)]
LIST_CALL_RESET = ["%dS" % i for i in range(0, 61)]
LIST_DTMF_TIME = ["%dMS" % (50 + i * 10) for i in range(0, 46)]
LIST_VFO_STEP = ["2.5K", "5K", "6.25K", "8.33K", "10K", "12.5K",
                 "25K", "50K", "100K"]
LIST_SP_MUTE = ["QT", "QT*DT", "QT+DT"]
LIST_DESCRAMBLE = ["Off"] + [str(i) for i in range(1, 9)]
LIST_CALL_ID = [str(i) for i in range(1, 21)]

# Combined tone list for VFO settings (Off, CTCSS x38, DCS-N x104, DCS-I x104)
LIST_TONE_SETTING = (["Off"] +
                     ["CTCSS %.1f" % t for t in chirp_common.TONES[:38]] +
                     ["DCS %03dN" % d for d in chirp_common.DTCS_CODES] +
                     ["DCS %03dI" % d for d in chirp_common.DTCS_CODES])


def _tone_to_setting_idx(tmode, tone_val):
    """Convert (tmode, 1-based tone index) to LIST_TONE_SETTING index."""
    if tmode == 0:
        return 0
    elif tmode == 1:
        return 1 + (tone_val - 1)
    elif tmode == 2:
        return 1 + 38 + (tone_val - 1)
    elif tmode == 3:
        return 1 + 38 + len(chirp_common.DTCS_CODES) + (tone_val - 1)
    return 0


def _setting_idx_to_tone(idx):
    """Convert LIST_TONE_SETTING index to (tmode, 1-based tone index)."""
    if idx == 0:
        return 0, 0
    idx -= 1
    if idx < 38:
        return 1, idx + 1
    idx -= 38
    if idx < len(chirp_common.DTCS_CODES):
        return 2, idx + 1
    idx -= len(chirp_common.DTCS_CODES)
    return 3, idx + 1

POWER_LEVELS = [chirp_common.PowerLevel("Low", watts=2.00),
                chirp_common.PowerLevel("High", watts=5.00)]


def _decode_name(raw_bytes):
    """Decode 6-byte EEPROM name using custom character encoding."""
    name = ""
    for b in raw_bytes:
        if b == 0xFF:
            break
        elif b == 0x29:
            name += " "
        elif b == 0x24:
            name += "-"
        elif 0x00 <= b <= 0x09:
            name += str(b)
        elif 0x0A <= b <= 0x23:
            name += chr(ord('A') + b - 0x0A)
    return name.rstrip()


def _encode_name(name, length=6):
    """Encode a name string to EEPROM custom character encoding."""
    result = []
    for ch in name.upper()[:length]:
        if ch == ' ':
            result.append(0x29)
        elif ch == '-':
            result.append(0x24)
        elif '0' <= ch <= '9':
            result.append(int(ch))
        elif 'A' <= ch <= 'Z':
            result.append(ord(ch) - ord('A') + 0x0A)
    while len(result) < length:
        result.append(0xFF)
    return result


class RollingXOR:
    """Rolling XOR stream cipher used by the KG-S88G serial protocol.

    The XOR key carries across all packets (TX and RX interleaved) within
    a session. Byte 0 of each packet is NOT encrypted but still advances
    through the cipher.
    """

    def __init__(self, key=0x00):
        self.key = key

    def process(self, data, skip_first=True):
        """Decrypt data. Byte 0 of each packet is NOT encrypted."""
        result = bytearray()
        start = 0
        if skip_first:
            result.append(data[0])
            start = 1
        for i in range(start, len(data)):
            enc_byte = data[i]
            result.append(enc_byte ^ self.key)
            self.key = (self.key + enc_byte) & 0xFF
        return bytes(result)

    def encrypt(self, data, skip_first=True):
        """Encrypt data. Byte 0 of each packet is NOT encrypted."""
        result = bytearray()
        start = 0
        if skip_first:
            result.append(data[0])
            start = 1
        for i in range(start, len(data)):
            plain_byte = data[i]
            enc_byte = plain_byte ^ self.key
            result.append(enc_byte)
            self.key = (self.key + enc_byte) & 0xFF
        return bytes(result)


def _send(serial, data):
    """Send data one byte at a time with a small delay, as the CPS does."""
    for byte in data:
        serial.write(bytes([byte]))
        time.sleep(0.002)


def _do_handshake(radio, magic):
    """Perform the handshake with the radio.

    Protocol (from CPS USB capture analysis):
    1. TX 8 bytes: 0x02 + magic (5 bytes) + 0xFF 0xFF  (plaintext)
    2. RX 1 byte: 0x06 ACK
    3. TX 16 bytes: key material (plaintext, NOT encrypted)
         key_material[0]  = 0xa5  (required magic byte, validated by radio)
         key_material[1]  = arbitrary byte A
         key_material[2]  = arbitrary byte
         key_material[3]  = arbitrary byte B
         key_material[4..7]  = arbitrary
         key_material[8..15] = arbitrary (radio echoes these back)
         data_phase_key   = A XOR B  (km[1] XOR km[3])
    4. RX 12 bytes: radio identity (mostly constant across sessions, plaintext)
    5. TX 1 byte: 0x06 ACK
    6. RX 18 bytes: key response — contains km[8..15] echoed at bytes [9..16]
    7. TX 1 byte: 0x06 ACK
    8. RX 1 byte: 0x06 final ACK

    The handshake is entirely plaintext. The rolling XOR cipher starts fresh
    at data_phase_key = km[1] XOR km[3] for the data transfer phase.

    Returns (cipher, has_echo).
    """
    serial = radio.pipe

    # Step 1: Send plaintext magic. Detect echo by inspecting first response
    # byte: 0x02 = our echo, 0x06 = radio ACK (no echo).
    handshake = b"\x02" + magic + b"\xff\xff"
    has_echo = False
    for attempt in range(5):
        LOG.debug("Handshake TX (attempt %d): %s" %
                  (attempt + 1, util.hexprint(handshake)))
        _send(serial, handshake)

        first = serial.read(1)
        LOG.debug("Handshake first byte: %s" %
                  (first.hex() if first else "none"))

        if not first:
            serial.flushInput()
            continue

        if first == b"\x06":
            has_echo = False
            LOG.debug("No USB echo detected")
            break
        elif first == handshake[0:1]:
            has_echo = True
            rest = serial.read(len(handshake) - 1 + 1)  # 7 echo + 1 ACK
            LOG.debug("Echo rest + ACK (%d bytes): %s" %
                      (len(rest), rest.hex() if rest else "none"))
            if len(rest) >= len(handshake) and rest[-1] == 0x06:
                LOG.debug("USB-serial echo detected")
                break
            serial.flushInput()
            continue
        else:
            LOG.debug("Unexpected first byte: 0x%02x" % first[0])
            serial.flushInput()
            continue
    else:
        raise errors.RadioError(
            "Radio did not ACK handshake after 5 attempts")

    # Step 3: Send key material as PLAINTEXT (not encrypted).
    # km[0] = 0xa5 is a required magic byte the radio validates.
    # km[1..3] determine the data-phase cipher key: key = km[1] XOR km[3].
    # Using km[1]=km[3]=0x00 gives data_phase_key = 0x00 (predictable).
    km = bytes([0xa5]) + b"\x00" * 15
    LOG.debug("Handshake TX key material: %s" % km.hex())
    _send(serial, km)
    if has_echo:
        serial.read(16)

    # Step 4: Read 12-byte identity response (mostly constant plaintext)
    resp1 = serial.read(12)
    if len(resp1) != 12:
        avail = serial.inWaiting()
        extra = serial.read(avail) if avail else b""
        raise errors.RadioError(
            "Radio did not send identity (got %d bytes: %s, "
            "buffer: %s)" % (len(resp1), resp1.hex() if resp1 else "none",
                             extra.hex() if extra else "none"))
    LOG.debug("Handshake RX identity: %s" % resp1.hex())

    # Step 5: ACK
    _send(serial, b"\x06")
    if has_echo:
        serial.read(1)

    # Step 6: Read 18-byte key response (bytes [9..16] echo km[8..15])
    resp2 = serial.read(18)
    if len(resp2) != 18:
        avail = serial.inWaiting()
        extra = serial.read(avail) if avail else b""
        raise errors.RadioError(
            "Radio did not send key response (got %d bytes: %s, "
            "buffer: %s)" % (len(resp2), resp2.hex() if resp2 else "none",
                             extra.hex() if extra else "none"))
    LOG.debug("Handshake RX key response: %s" % resp2.hex())

    # Step 7: ACK
    _send(serial, b"\x06")
    if has_echo:
        serial.read(1)

    # Step 8: Final ACK
    final = serial.read(1)
    if len(final) != 1 or final[0] != 0x06:
        raise errors.RadioError(
            "Radio did not send final ACK (got %s)" %
            (final.hex() if final else "nothing"))

    # Derive data-phase cipher key from key material
    data_phase_key = km[1] ^ km[3]  # = 0x00 XOR 0x00 = 0x00
    cipher = RollingXOR(data_phase_key)
    LOG.debug("Handshake complete, data_phase_key=0x%02x, echo=%s" %
              (data_phase_key, has_echo))

    return cipher, has_echo


def do_download(radio):
    """Download memory image from the radio."""
    serial = radio.pipe
    serial.timeout = 1

    time.sleep(0.5)
    serial.flushInput()

    cipher, has_echo = _do_handshake(radio, b"RWITF")

    data = bytearray()
    status = chirp_common.Status()
    status.msg = "Cloning from radio"
    status.cur = 0
    status.max = radio._memsize

    for addr in range(0x0000, 0x27D0, 0x10):
        # Build TX: [0x57][addr_hi][addr_mid][addr_lo][0x10]
        tx = bytes([0x57,
                    (addr >> 16) & 0xFF,
                    (addr >> 8) & 0xFF,
                    addr & 0xFF,
                    0x10])
        enc_tx = cipher.encrypt(tx, skip_first=True)
        _send(serial, enc_tx)
        if has_echo:
            serial.read(5)

        # Read 21-byte RX
        rx = serial.read(21)
        if len(rx) != 21:
            raise errors.RadioError(
                "Short read at address %04x (got %d bytes)" % (addr, len(rx)))
        dec_rx = cipher.process(rx, skip_first=True)

        # Verify address echo
        rx_addr = (dec_rx[1] << 16) | (dec_rx[2] << 8) | dec_rx[3]
        if rx_addr != addr:
            raise errors.RadioError(
                "Address mismatch at %04x (got %04x)" % (addr, rx_addr))

        data.extend(dec_rx[5:])

        status.cur = addr + 0x10
        radio.status_fn(status)

    # Send terminate byte
    term = cipher.encrypt(bytes([0x54]), skip_first=True)
    _send(serial, term)

    return memmap.MemoryMapBytes(bytes(data))


def do_upload(radio):
    """Upload memory image to the radio."""
    serial = radio.pipe
    serial.timeout = 1

    time.sleep(0.5)
    serial.flushInput()

    cipher, has_echo = _do_handshake(radio, b"WRITF")

    mmap = radio.get_mmap()

    # Recompute channel presence bitmaps from actual channel data.
    # The radio maintains a 50-byte bitmap at 0x2500 (and a copy at 0x2600)
    # where channel CH is active when bit (CH % 8) of byte (CH // 8) is set.
    # If this bitmap doesn't match the written channel data the radio silently
    # ignores channels that are not listed in it.
    bitmap = bytearray(50)
    for ch in range(1, 401):
        ch_off = 0x0100 + ch * 16
        rx_bytes = bytes(mmap[ch_off:ch_off + 4])
        if rx_bytes not in (b'\xff\xff\xff\xff', b'\x00\x00\x00\x00'):
            bitmap[ch // 8] |= (1 << (ch % 8))
    for i, b in enumerate(bitmap):
        mmap[0x2500 + i] = b
        mmap[0x2600 + i] = b

    status = chirp_common.Status()
    status.msg = "Cloning to radio"
    status.cur = 0
    status.max = radio._memsize

    for addr in range(0x0000, 0x27D0, 0x10):
        chunk = bytes(mmap[addr:addr + 0x10])

        # Build 21-byte write packet: [0x57][addr_hi][addr_mid][addr_lo][0x10][16 data]
        tx = bytes([0x57,
                    (addr >> 16) & 0xFF,
                    (addr >> 8) & 0xFF,
                    addr & 0xFF,
                    0x10]) + chunk
        enc_tx = cipher.encrypt(tx, skip_first=True)
        _send(serial, enc_tx)
        if has_echo:
            serial.read(21)

        # Radio ACKs each block with a plain (unencrypted) 0x06
        ack = serial.read(1)
        if len(ack) != 1 or ack[0] != 0x06:
            raise errors.RadioError(
                "Radio did not ACK write at address 0x%04x (got %s)" %
                (addr, ack.hex() if ack else "nothing"))

        status.cur = addr + 0x10
        radio.status_fn(status)





@directory.register
class KGS88GRadio(chirp_common.CloneModeRadio,
                  chirp_common.ExperimentalRadio):
    """Wouxun KG-S88G"""
    VENDOR = "Wouxun"
    MODEL = "KG-S88G"
    BAUD_RATE = 9600
    _memsize = 0x27D0
    _num_channels = 400

    def get_features(self):
        rf = chirp_common.RadioFeatures()
        rf.has_settings = True
        rf.has_bank = False
        rf.has_ctone = True
        rf.has_cross = True
        rf.has_rx_dtcs = True
        rf.has_tuning_step = False
        rf.has_name = True
        rf.can_odd_split = True
        rf.valid_name_length = 6
        rf.valid_characters = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ- "
        rf.valid_skips = []
        rf.valid_tmodes = ["", "Tone", "TSQL", "DTCS", "Cross"]
        rf.valid_cross_modes = ["Tone->Tone", "Tone->DTCS", "DTCS->Tone",
                                "->Tone", "->DTCS", "DTCS->", "DTCS->DTCS"]
        rf.valid_dtcs_codes = sorted(DTCS_CODES)
        rf.valid_power_levels = POWER_LEVELS
        rf.valid_duplexes = ["", "-", "+", "split", "off"]
        rf.valid_modes = ["FM", "NFM"]
        rf.memory_bounds = (1, self._num_channels)
        rf.valid_tuning_steps = [2.5, 5., 6.25, 10., 12.5, 25.]
        rf.valid_bands = [(400000000, 520000000)]
        rf.valid_tones = TONES[:38]
        return rf

    def process_mmap(self):
        self._memobj = bitwise.parse(MEM_FORMAT, self._mmap)

    def sync_in(self):
        """Download from radio"""
        try:
            data = do_download(self)
        except errors.RadioError:
            raise
        except Exception as e:
            LOG.exception('Unexpected error during download')
            raise errors.RadioError(
                'Unexpected error communicating with the radio: %s' % e)
        self._mmap = data
        self.process_mmap()

    def sync_out(self):
        """Upload to radio"""
        try:
            do_upload(self)
        except errors.RadioError:
            raise
        except Exception as e:
            LOG.exception('Unexpected error during upload')
            raise errors.RadioError(
                'Unexpected error communicating with the radio: %s' % e)

    def get_raw_memory(self, number):
        return repr(self._memobj.memory[number])

    def _get_tone(self, mem, _mem):
        """Decode tone settings from EEPROM to CHIRP memory object."""
        rx_tone = tx_tone = None

        tx_tmode = TMODES[_mem.tx_tmode]
        rx_tmode = TMODES[_mem.rx_tmode]

        if tx_tmode == "Tone":
            tx_tone = TONES[_mem.tx_tone - 1]
        elif tx_tmode == "DTCS":
            tx_tone = DTCS_CODES[_mem.tx_tone - 1]

        if rx_tmode == "Tone":
            rx_tone = TONES[_mem.rx_tone - 1]
        elif rx_tmode == "DTCS":
            rx_tone = DTCS_CODES[_mem.rx_tone - 1]

        tx_pol = "R" if _mem.tx_tmode == 0x03 else "N"
        rx_pol = "R" if _mem.rx_tmode == 0x03 else "N"

        chirp_common.split_tone_decode(mem, (tx_tmode, tx_tone, tx_pol),
                                       (rx_tmode, rx_tone, rx_pol))

    def _set_tone(self, mem, _mem):
        """Encode CHIRP tone settings back to EEPROM format."""
        ((txmode, txtone, txpol),
         (rxmode, rxtone, rxpol)) = chirp_common.split_tone_encode(mem)

        _mem.tx_tmode = TMODES.index(txmode)
        _mem.rx_tmode = TMODES.index(rxmode)

        if txmode == "Tone":
            _mem.tx_tone = TONES.index(txtone) + 1
        elif txmode == "DTCS":
            _mem.tx_tmode = 0x03 if txpol == "R" else 0x02
            _mem.tx_tone = DTCS_CODES.index(txtone) + 1

        if rxmode == "Tone":
            _mem.rx_tone = TONES.index(rxtone) + 1
        elif rxmode == "DTCS":
            _mem.rx_tmode = 0x03 if rxpol == "R" else 0x02
            _mem.rx_tone = DTCS_CODES.index(rxtone) + 1

    def _is_txinh(self, _mem):
        raw_tx = b""
        for i in range(0, 4):
            raw_tx += _mem.txfreq[i].get_raw()
        return raw_tx == b"\xFF\xFF\xFF\xFF"

    def get_memory(self, number):
        _mem = self._memobj.memory[number]
        _nam = self._memobj.names[number]

        mem = chirp_common.Memory()
        mem.number = number

        mem.freq = int(_mem.rxfreq) * 10

        # Empty channel detection
        if mem.freq == 0:
            mem.empty = True
            return mem

        if _mem.rxfreq.get_raw() == b"\xFF\xFF\xFF\xFF":
            mem.freq = 0
            mem.empty = True
            return mem

        # Duplex / offset
        if self._is_txinh(_mem):
            mem.duplex = "off"
            mem.offset = 0
        elif int(_mem.rxfreq) == int(_mem.txfreq):
            mem.duplex = ""
            mem.offset = 0
        elif abs(int(_mem.rxfreq) * 10 - int(_mem.txfreq) * 10) > 70000000:
            mem.duplex = "split"
            mem.offset = int(_mem.txfreq) * 10
        else:
            mem.duplex = "+" if int(_mem.txfreq) > int(_mem.rxfreq) else "-"
            mem.offset = abs(int(_mem.rxfreq) - int(_mem.txfreq)) * 10

        # Wide/narrow
        mem.mode = "FM" if _mem.wide else "NFM"

        # Channel name (custom encoding)
        mem.name = _decode_name([int(_nam.name[i]) for i in range(6)])

        # Tones
        self._get_tone(mem, _mem)

        # TX power
        try:
            mem.power = POWER_LEVELS[_mem.highpower]
        except IndexError:
            LOG.error("Radio reported invalid power level %s" %
                      _mem.highpower)
            mem.power = POWER_LEVELS[0]

        # Per-channel extras
        mem.extra = RadioSettingGroup("extra", "Extra")

        rs = RadioSetting("busy_lock", "Busy Lock",
                          RadioSettingValueBoolean(bool(_mem.busy_lock)))
        rs.set_doc("Prevent transmitting when the channel is in use "
                   "(carrier detected).")
        mem.extra.append(rs)

        rs = RadioSetting("call_id", "Call ID",
                          RadioSettingValueList(
                              LIST_CALL_ID,
                              current_index=max(0, int(_mem.call_id) - 1)))
        rs.set_doc("DTMF Call ID entry (1-20) associated with this channel, "
                   "used for selective calling.")
        mem.extra.append(rs)

        rs = RadioSetting("sp_mute", "SP Mute",
                          RadioSettingValueList(
                              LIST_SP_MUTE,
                              current_index=min(int(_mem.sp_mute),
                                                len(LIST_SP_MUTE) - 1)))
        rs.set_doc("Speaker mute mode: QT=tone squelch only, "
                   "QT*DT=tone AND digital, QT+DT=tone OR digital.")
        mem.extra.append(rs)

        rs = RadioSetting("descramble", "Descramble",
                          RadioSettingValueList(
                              LIST_DESCRAMBLE,
                              current_index=min(int(_mem.descramble),
                                                len(LIST_DESCRAMBLE) - 1)))
        rs.set_doc("Audio descrambler code (Off, or 1-8). Must match the "
                   "transmitting radio's scramble setting.")
        mem.extra.append(rs)

        byte_idx = number // 8
        bit_idx = number % 8
        is_fav = bool(int(self._memobj.favorites.map[byte_idx]) &
                      (1 << bit_idx))
        rs = RadioSetting("favorite", "Favorite",
                          RadioSettingValueBoolean(is_fav))
        rs.set_doc("Mark this channel as a favorite. Favorites can be "
                   "quickly accessed using the Favorite function key.")
        mem.extra.append(rs)

        return mem

    def set_memory(self, mem):
        _mem = self._memobj.memory[mem.number]
        _nam = self._memobj.names[mem.number]

        if mem.empty:
            _mem.set_raw(b"\xFF" * (_mem.size() // 8))
            for i in range(6):
                _nam.name[i] = 0xFF
            return

        _mem.set_raw(b"\x00" * (_mem.size() // 8))

        # call_id must be non-zero for the radio to treat the channel as active.
        # Default to 1; overridden below if mem.extra carries a value.
        _mem.call_id = 1

        # Frequency
        _mem.rxfreq = mem.freq / 10

        if mem.duplex == "off":
            for i in range(0, 4):
                _mem.txfreq[i].set_raw(b"\xFF")
        elif mem.duplex == "split":
            _mem.txfreq = mem.offset / 10
        elif mem.duplex == "+":
            _mem.txfreq = (mem.freq + mem.offset) / 10
        elif mem.duplex == "-":
            _mem.txfreq = (mem.freq - mem.offset) / 10
        else:
            _mem.txfreq = mem.freq / 10

        # Wide/narrow
        _mem.wide = 1 if mem.mode == "FM" else 0

        # Channel name
        encoded = _encode_name(mem.name, 6)
        for i in range(6):
            _nam.name[i] = encoded[i]

        # Tones
        self._set_tone(mem, _mem)

        # TX power
        if mem.power:
            _mem.highpower = POWER_LEVELS.index(mem.power)
        else:
            _mem.highpower = 1  # Default to high

        # Per-channel extras
        if mem.extra:
            for setting in mem.extra:
                name = setting.get_name()
                val = setting.value
                if name == "busy_lock":
                    _mem.busy_lock = 1 if bool(val) else 0
                elif name == "call_id":
                    idx = val.get_options().index(str(val))
                    _mem.call_id = idx + 1  # 1-indexed
                elif name == "sp_mute":
                    _mem.sp_mute = val.get_options().index(str(val))
                elif name == "descramble":
                    _mem.descramble = val.get_options().index(str(val))
                elif name == "favorite":
                    byte_idx = mem.number // 8
                    bit_idx = mem.number % 8
                    cur = int(self._memobj.favorites.map[byte_idx])
                    if bool(val):
                        cur |= (1 << bit_idx)
                    else:
                        cur &= ~(1 << bit_idx)
                    self._memobj.favorites.map[byte_idx] = cur

    def get_settings(self):
        try:
            return self._get_settings()
        except Exception:
            LOG.exception("Failed to parse settings")
            return None

    def _get_settings(self):
        _s = self._memobj.settings
        _v = self._memobj.vfo

        basic = RadioSettingGroup("basic", "Basic Settings")
        timers = RadioSettingGroup("timers", "Timers")
        scan = RadioSettingGroup("scan", "Scan")
        audio = RadioSettingGroup("audio", "Audio")
        lock = RadioSettingGroup("lock", "Lock")
        vox = RadioSettingGroup("vox", "VOX")
        pfkeys = RadioSettingGroup("pfkeys", "PF Keys")
        dtmf = RadioSettingGroup("dtmf", "DTMF")
        vfo_grp = RadioSettingGroup("vfo", "Frequency Mode")
        options = RadioSettingGroup("options", "Options")
        top = RadioSettings(basic, timers, scan, audio, lock, vox,
                            pfkeys, dtmf, vfo_grp, options)

        def rs(name, label, val, doc=None):
            """Shorthand to build a RadioSetting with optional doc."""
            r = RadioSetting(name, label, val)
            if doc:
                r.set_doc(doc)
            return r

        # ── Basic ──────────────────────────────────────────────────────────
        basic.append(rs(
            "settings.squelch", "Squelch",
            RadioSettingValueInteger(0, 9, int(_s.squelch)),
            "Squelch threshold (0=open, 9=tightest). Higher values require "
            "stronger signals to open the squelch."))

        basic.append(rs(
            "settings.beep", "Beep",
            RadioSettingValueBoolean(bool(_s.beep)),
            "Enable keypad beep tones."))

        basic.append(rs(
            "settings.battery_save", "Battery Save",
            RadioSettingValueBoolean(bool(_s.battery_save)),
            "Reduce power consumption when idle by periodically turning off "
            "the receiver."))

        basic.append(rs(
            "settings.voice", "Voice Guide",
            RadioSettingValueBoolean(bool(_s.voice)),
            "Announce menu selections and status changes by voice."))

        basic.append(rs(
            "settings.work_mode", "Work Mode",
            RadioSettingValueList(LIST_WORK_MODE,
                                  current_index=int(_s.work_mode)),
            "Channel display mode: Freq=frequency only, Ch/Freq=channel "
            "number and frequency, Ch/Num=channel number only, "
            "Ch/Name=channel name."))

        basic.append(rs(
            "settings.startup_display", "Startup Display",
            RadioSettingValueList(LIST_STARTUP_DISPLAY,
                                  current_index=int(_s.startup_display)),
            "What to show on screen at power-on: startup message text "
            "or battery voltage."))

        basic.append(rs(
            "settings.backlight", "Backlight Timer",
            RadioSettingValueList(LIST_BACKLIGHT,
                                  current_index=int(_s.backlight)),
            "How long the backlight stays illuminated before automatically "
            "turning off. Always keeps the backlight permanently on."))

        basic.append(rs(
            "settings.active_channel", "Active Channel",
            RadioSettingValueInteger(1, 400, int(_s.active_channel)),
            "The channel the radio will be on when powered on (1-400)."))

        # Startup message (7-char EEPROM encoding)
        msg = _decode_name([int(_s.startup_msg[i]) for i in range(7)])
        val = RadioSettingValueString(0, 7, msg)
        r = RadioSetting("startup_msg", "Startup Message", val)
        r.set_doc("Text shown at power-on when Startup Display is set to "
                  "Message. Up to 7 characters (A-Z, 0-9, space, hyphen).")

        def apply_startup_msg(setting, obj):
            encoded = _encode_name(str(setting.value), 7)
            for i in range(7):
                obj.settings.startup_msg[i] = encoded[i]

        r.set_apply_callback(apply_startup_msg, self._memobj)
        basic.append(r)

        # VFO step
        step_val = min(int(_s.vfo_step), len(LIST_VFO_STEP) - 1)
        basic.append(rs(
            "settings.vfo_step", "VFO Step",
            RadioSettingValueList(LIST_VFO_STEP, current_index=step_val),
            "Frequency tuning step size used in VFO/Frequency mode."))

        # ── Timers ─────────────────────────────────────────────────────────
        tot_val = min(int(_s.tot), len(LIST_TOT) - 1)
        timers.append(rs(
            "settings.tot", "Timeout Timer (TOT)",
            RadioSettingValueList(LIST_TOT, current_index=tot_val),
            "Automatically stop transmitting after this duration to prevent "
            "accidental long transmissions. Off disables the timer."))

        timers.append(rs(
            "settings.toa", "Timeout Alarm (TOA)",
            RadioSettingValueInteger(0, 10, int(_s.toa)),
            "Seconds before TOT expires at which an audible alarm sounds "
            "to warn you to release PTT. 0 disables the alarm."))

        al_val = min(int(_s.auto_lock), len(LIST_AUTO_LOCK) - 1)

        # ── Scan ───────────────────────────────────────────────────────────
        scan_val = min(int(_s.scan_mode), len(LIST_SCAN_MODE) - 1)
        scan.append(rs(
            "settings.scan_mode", "Scan Mode",
            RadioSettingValueList(LIST_SCAN_MODE, current_index=scan_val),
            "Scan resume behavior: CO=carrier operated (resume after signal "
            "drops), TO=time operated (resume after timeout), "
            "SE=search (stop on signal)."))

        scan.append(rs(
            "settings.scan_qt", "Scan QT",
            RadioSettingValueBoolean(bool(_s.scan_qt)),
            "When enabled, the scanner only stops on channels whose "
            "CTCSS/DCS tone matches the receive tone setting."))

        scan.append(rs(
            "settings.priority_scan", "Priority Scan",
            RadioSettingValueBoolean(bool(_s.priority_scan)),
            "Periodically check the priority channel while scanning "
            "other channels."))

        scan.append(rs(
            "settings.priority_channel", "Priority Channel",
            RadioSettingValueInteger(1, 400, int(_s.priority_channel)),
            "Channel to check when Priority Scan is enabled (1-400)."))

        # ── Audio ──────────────────────────────────────────────────────────
        roger_val = min(int(_s.roger), len(LIST_ROGER) - 1)
        audio.append(rs(
            "settings.roger", "Roger Beep",
            RadioSettingValueList(LIST_ROGER, current_index=roger_val),
            "Play a beep tone at the beginning (BOT), end (EOT), or both "
            "ends of each transmission. Useful to signal PTT release."))

        alert_val = min(int(_s.alert_tone), len(LIST_ALERT_TONE) - 1)
        audio.append(rs(
            "settings.alert_tone", "Alert Tone",
            RadioSettingValueList(LIST_ALERT_TONE, current_index=alert_val),
            "Frequency of the alert/call tones used for DTMF calls "
            "and alarms."))

        ts_val = min(int(_s.tone_save), len(LIST_TONE_SAVE) - 1)
        audio.append(rs(
            "settings.tone_save", "Tone Save",
            RadioSettingValueList(LIST_TONE_SAVE, current_index=ts_val),
            "Which CTCSS/DCS tones to save/display when using Scan QT: "
            "RX tone only, TX tone only, or both TX and RX."))

        # ── Lock ───────────────────────────────────────────────────────────
        lock.append(rs(
            "settings.auto_lock", "Auto Lock",
            RadioSettingValueList(LIST_AUTO_LOCK, current_index=al_val),
            "Automatically lock the keypad after this period of inactivity. "
            "Off disables auto-lock."))

        lm_val = min(int(_s.lock_mode), len(LIST_LOCK_MODE) - 1)
        lock.append(rs(
            "settings.lock_mode", "Lock Mode",
            RadioSettingValueList(LIST_LOCK_MODE, current_index=lm_val),
            "What the keypad lock covers: Key=keypad only, "
            "Key+PTT=keypad and PTT, Key+Enc=keypad and encoder dial, "
            "Key+All=all controls."))

        # ── VOX ────────────────────────────────────────────────────────────
        vox_val = min(int(_s.vox), len(LIST_OFF_1_9) - 1)
        vox.append(rs(
            "settings.vox", "VOX",
            RadioSettingValueList(LIST_OFF_1_9, current_index=vox_val),
            "Voice-operated transmit sensitivity (1=most sensitive, "
            "9=least sensitive). Off disables VOX."))

        vd_val = max(0, min(int(_s.vox_delay) - 1, len(LIST_VOX_DELAY) - 1))
        vox.append(rs(
            "settings.vox_delay", "VOX Delay",
            RadioSettingValueList(LIST_VOX_DELAY, current_index=vd_val),
            "How long the radio continues transmitting after voice stops "
            "before releasing PTT."))

        # ── PF Keys ────────────────────────────────────────────────────────
        pf_doc = ("Programmable function key assignment. Available functions: "
                  "Scan, Backlight, VOX, TX Power, Call, Talk-Around, "
                  "Flashlight, Monitor, Reverse, WorkMode, Alarm, SOS, "
                  "Favorite.")

        def pf_setting(name, label, val):
            idx = max(0, min(int(val) - 1, len(LIST_PF_KEY) - 1))
            r = RadioSetting(name, label,
                             RadioSettingValueList(LIST_PF_KEY,
                                                   current_index=idx))
            r.set_doc(pf_doc)
            return r

        pfkeys.append(pf_setting("settings.pf_top_long",  "TOP Long",
                                 _s.pf_top_long))
        pfkeys.append(pf_setting("settings.pf_top_short", "TOP Short",
                                 _s.pf_top_short))
        pfkeys.append(pf_setting("settings.pf1_short",    "PF1 Short",
                                 _s.pf1_short))
        pfkeys.append(pf_setting("settings.pf1_long",     "PF1 Long",
                                 _s.pf1_long))
        pfkeys.append(pf_setting("settings.pf2_short",    "PF2 Short",
                                 _s.pf2_short))
        pfkeys.append(pf_setting("settings.pf2_long",     "PF2 Long",
                                 _s.pf2_long))

        # ── DTMF ───────────────────────────────────────────────────────────
        st_val = min(int(_s.sidetone), len(LIST_SIDETONE) - 1)
        dtmf.append(rs(
            "settings.sidetone", "Sidetone",
            RadioSettingValueList(LIST_SIDETONE, current_index=st_val),
            "DTMF sidetone mode: DT-ST=DTMF tones only, ANI-ST=ANI ID "
            "tones only, DT+ANI=both. Off disables sidetone."))

        pid_val = min(int(_s.ptt_id), len(LIST_PTT_ID) - 1)
        dtmf.append(rs(
            "settings.ptt_id", "PTT-ID",
            RadioSettingValueList(LIST_PTT_ID, current_index=pid_val),
            "Automatically transmit the radio's DTMF ID at the beginning "
            "(BOT), end (EOT), or both ends of each transmission."))

        id_dly_val = max(0, min(int(_s.id_dly) - 1, len(LIST_ID_DLY) - 1))
        dtmf.append(rs(
            "settings.id_dly", "ID Delay",
            RadioSettingValueList(LIST_ID_DLY, current_index=id_dly_val),
            "Delay between PTT press and DTMF ID transmission when "
            "PTT-ID is set to BOT or BOTH."))

        ring_val = min(int(_s.ring), len(LIST_RING) - 1)
        dtmf.append(rs(
            "settings.ring", "Ring",
            RadioSettingValueList(LIST_RING, current_index=ring_val),
            "Duration of the alert tone when a DTMF call is received. "
            "Off disables the ring alert."))

        cr_val = min(int(_s.call_reset), len(LIST_CALL_RESET) - 1)
        dtmf.append(rs(
            "settings.call_reset", "Call Reset Time",
            RadioSettingValueList(LIST_CALL_RESET, current_index=cr_val),
            "Time after which an unanswered DTMF call alert resets "
            "(0-60 seconds)."))

        tx_val = min(int(_s.dtmf_tx_time), len(LIST_DTMF_TIME) - 1)
        dtmf.append(rs(
            "settings.dtmf_tx_time", "DTMF TX Time",
            RadioSettingValueList(LIST_DTMF_TIME, current_index=tx_val),
            "Duration of each DTMF tone during transmission "
            "(50-500 ms)."))

        iv_val = min(int(_s.dtmf_interval), len(LIST_DTMF_TIME) - 1)
        dtmf.append(rs(
            "settings.dtmf_interval", "DTMF Interval",
            RadioSettingValueList(LIST_DTMF_TIME, current_index=iv_val),
            "Pause between consecutive DTMF tones during transmission "
            "(50-500 ms)."))

        dtmf.append(rs(
            "settings.be_control", "Be Control",
            RadioSettingValueBoolean(bool(_s.be_control)),
            "Enable call control via DTMF beep codes."))

        # ID-EDIT: 4-byte DTMF identity, last byte is 'F' terminator
        id_edit_raw = [int(_s.id_edit[i]) for i in range(4)]
        id_edit_str = _decode_name(id_edit_raw).rstrip('F')
        r = RadioSetting("id_edit", "ID-EDIT",
                         RadioSettingValueString(0, 3, id_edit_str))
        r.set_doc("This radio's DTMF identity code (up to 3 digits). "
                  "Used for PTT-ID transmission and DTMF call identification.")

        def apply_id_edit(setting, obj):
            encoded = _encode_name(str(setting.value) + 'F', 4)
            for i in range(4):
                obj.settings.id_edit[i] = encoded[i]

        r.set_apply_callback(apply_id_edit, self._memobj)
        dtmf.append(r)

        # CALL IDs 1-20
        for i in range(20):
            cid_raw = [int(self._memobj.callids[i].id[j]) for j in range(6)]
            cid_str = _decode_name(cid_raw)
            r = RadioSetting(
                "callids[%d].id" % i, "CALL ID%d" % (i + 1),
                RadioSettingValueString(0, 6, cid_str))
            r.set_doc("DTMF call ID entry %d (up to 6 digits, 0-9). "
                      "Used for selective calling." % (i + 1))

            def apply_callid(setting, obj, idx=i):
                encoded = _encode_name(str(setting.value), 6)
                for j in range(6):
                    obj.callids[idx].id[j] = encoded[j]

            r.set_apply_callback(apply_callid, self._memobj)
            dtmf.append(r)

        # ── Frequency Mode (VFO) ───────────────────────────────────────────
        vfo_freq_mhz = "%.5f" % (int(_v.rxfreq) * 10 / 1e6)
        r = RadioSetting("vfo.rxfreq", "Frequency (MHz)",
                         RadioSettingValueString(0, 10, vfo_freq_mhz))
        r.set_doc("VFO receive (and simplex transmit) frequency in MHz, "
                  "e.g. 462.56250. The TX frequency is set separately when "
                  "using a repeater offset.")

        def apply_vfo_rxfreq(setting, obj):
            try:
                hz = int(round(float(str(setting.value)) * 1e6))
                obj.vfo.rxfreq = hz // 10
                # Keep TX in sync for simplex; user enables Repeater on the
                # radio itself if a split TX frequency is needed.
                obj.vfo.txfreq = hz // 10
            except ValueError:
                pass

        r.set_apply_callback(apply_vfo_rxfreq, self._memobj)
        vfo_grp.append(r)

        vfo_grp.append(rs(
            "settings.repeater", "Repeater",
            RadioSettingValueBoolean(bool(_s.repeater)),
            "Enable repeater offset in VFO mode. When on, the radio "
            "transmits on a different frequency than it receives on. "
            "Configure the TX frequency on the radio itself."))

        rx_tone_idx = _tone_to_setting_idx(int(_v.rx_tmode), int(_v.rx_tone))
        r = RadioSetting(
            "vfo_rx_tone", "RX CTCSS/DCS",
            RadioSettingValueList(LIST_TONE_SETTING,
                                  current_index=rx_tone_idx))
        r.set_doc("Receive CTCSS/DCS tone squelch for VFO mode. "
                  "Off=carrier squelch, CTCSS/DCS=tone squelch.")

        def apply_vfo_rx_tone(setting, obj):
            idx = setting.value.get_options().index(str(setting.value))
            tmode, tone = _setting_idx_to_tone(idx)
            obj.vfo.rx_tmode = tmode
            obj.vfo.rx_tone = tone

        r.set_apply_callback(apply_vfo_rx_tone, self._memobj)
        vfo_grp.append(r)

        tx_tone_idx = _tone_to_setting_idx(int(_v.tx_tmode), int(_v.tx_tone))
        r = RadioSetting(
            "vfo_tx_tone", "TX CTCSS/DCS",
            RadioSettingValueList(LIST_TONE_SETTING,
                                  current_index=tx_tone_idx))
        r.set_doc("Transmit CTCSS/DCS tone for VFO mode. "
                  "Select the tone required by the repeater or other station.")

        def apply_vfo_tx_tone(setting, obj):
            idx = setting.value.get_options().index(str(setting.value))
            tmode, tone = _setting_idx_to_tone(idx)
            obj.vfo.tx_tmode = tmode
            obj.vfo.tx_tone = tone

        r.set_apply_callback(apply_vfo_tx_tone, self._memobj)
        vfo_grp.append(r)

        vfo_grp.append(rs(
            "vfo.highpower", "Power",
            RadioSettingValueList(["Low", "High"],
                                  current_index=int(_v.highpower)),
            "Transmit power level in VFO mode. High=5W, Low=2W."))

        vfo_grp.append(rs(
            "vfo.wide", "Wide/Narrow",
            RadioSettingValueList(["Narrow", "Wide"],
                                  current_index=int(_v.wide)),
            "Channel bandwidth in VFO mode. Wide=25 kHz (FM), "
            "Narrow=12.5 kHz (NFM)."))

        vfo_grp.append(rs(
            "vfo.busy_lock", "Busy Lock",
            RadioSettingValueBoolean(bool(_v.busy_lock)),
            "Prevent transmitting when the channel is already in use "
            "(carrier detected) in VFO mode."))

        sm_val = min(int(_v.sp_mute), len(LIST_SP_MUTE) - 1)
        vfo_grp.append(rs(
            "vfo.sp_mute", "SP Mute",
            RadioSettingValueList(LIST_SP_MUTE, current_index=sm_val),
            "Speaker mute mode: QT=mute on tone squelch only, "
            "QT*DT=mute on tone AND digital squelch, "
            "QT+DT=mute on tone OR digital squelch."))

        dc_val = min(int(_v.descramble), len(LIST_DESCRAMBLE) - 1)
        vfo_grp.append(rs(
            "vfo.descramble", "Descramble",
            RadioSettingValueList(LIST_DESCRAMBLE, current_index=dc_val),
            "Audio descrambler setting (0=Off, 1-8 select scramble code). "
            "Must match the transmitting radio's scramble setting."))

        cid_val = max(0, min(int(_v.call_id) - 1, len(LIST_CALL_ID) - 1))
        vfo_grp.append(rs(
            "vfo.call_id", "Call ID",
            RadioSettingValueList(LIST_CALL_ID, current_index=cid_val),
            "Which CALL ID entry (1-20) this VFO channel uses for "
            "DTMF identification."))

        # ── Options ────────────────────────────────────────────────────────
        options.append(rs(
            "settings.timer", "Timer",
            RadioSettingValueBoolean(bool(_s.timer)),
            "Enable the transmission timer function."))

        options.append(rs(
            "settings.rpt_rct", "RPT RCT",
            RadioSettingValueBoolean(bool(_s.rpt_rct)),
            "Repeater Roger Code Tone — transmit a tone when releasing "
            "the repeater to signal end of transmission."))

        return top

    def set_settings(self, settings):
        for element in settings:
            if not isinstance(element, RadioSetting):
                self.set_settings(element)
                continue
            try:
                if element.has_apply_callback():
                    element.run_apply_callback()
                    continue

                name = element.get_name()
                if "." not in name:
                    # No dot = handled by apply_callback above; skip
                    continue
                # e.g. "settings.squelch" -> self._memobj.settings.squelch
                # or  "vfo.highpower"     -> self._memobj.vfo.highpower
                obj = self._memobj
                parts = name.split(".")
                for part in parts[:-1]:
                    if "[" in part and "]" in part:
                        attr, idx = part.rstrip("]").split("[")
                        obj = getattr(obj, attr)[int(idx)]
                    else:
                        obj = getattr(obj, part)
                field = parts[-1]

                val = element.value
                # List values: convert to index
                if isinstance(val, RadioSettingValueList):
                    raw = val.get_options().index(str(val))
                    # Voice is stored as 0 or 2 (not 0/1)
                    if field == "voice":
                        raw = 2 if raw else 0
                    # PF keys and call_id are 1-indexed
                    elif field in ("pf_top_long", "pf_top_short", "pf1_short",
                                   "pf1_long", "pf2_short", "pf2_long",
                                   "call_id"):
                        raw = raw + 1
                    # VOX delay stored as 1-5
                    elif field == "vox_delay":
                        raw = raw + 1
                    # ID DLY stored as 1-30
                    elif field == "id_dly":
                        raw = raw + 1
                    setattr(obj, field, raw)
                elif isinstance(val, RadioSettingValueBoolean):
                    setattr(obj, field, 1 if bool(val) else 0)
                elif isinstance(val, RadioSettingValueInteger):
                    setattr(obj, field, int(val))
            except Exception:
                LOG.exception("Failed to set setting %s", element.get_name())

    @classmethod
    def match_model(cls, filedata, filename):
        return False
