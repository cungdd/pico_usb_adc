// SPDX-License-Identifier: MIT
/*
 * Copyright 2021 Álvaro Fernández Rojas <noltari@gmail.com>
 */

#include <hardware/irq.h>
#include <hardware/structs/sio.h>
#include <hardware/uart.h>
#include <hardware/gpio.h>
#include "hardware/adc.h"
#include <pico/multicore.h>
#include <pico/stdlib.h>
#include <string.h>
#include <tusb.h>

#include "bsp/board_api.h"

#include "usb_descriptors.h"

#if !defined(MIN)
#define MIN(a, b) ((a > b) ? b : a)
#endif /* MIN */

#define LED_PIN PICO_DEFAULT_LED_PIN

#define BUFFER_SIZE 2560

typedef struct
{
  cdc_line_coding_t usb_lc;
  cdc_line_coding_t uart_lc;
  mutex_t lc_mtx;
  uint8_t uart_buffer[BUFFER_SIZE];
  uint32_t uart_pos;
  mutex_t uart_mtx;
  uint8_t usb_buffer[BUFFER_SIZE];
  uint32_t usb_pos;
  mutex_t usb_mtx;
} uart_data_t;

uart_data_t UART_DATA[CFG_TUD_CDC];

void usb_read_bytes(uint8_t itf)
{
  uart_data_t *ud = &UART_DATA[itf];
  uint32_t len = tud_cdc_n_available(itf);

  if (len &&
      mutex_try_enter(&ud->usb_mtx, NULL))
  {
    len = MIN(len, BUFFER_SIZE - ud->usb_pos);
    if (len)
    {
      uint32_t count;

      count = tud_cdc_n_read(itf, &ud->usb_buffer[ud->usb_pos], len);
      // tud_cdc_n_write(itf, &ud->usb_buffer[ud->usb_pos], count);
      // tud_cdc_n_write_flush(itf);
      ud->usb_pos += count;
    }

    mutex_exit(&ud->usb_mtx);
  }
}

void usb_write_bytes(uint8_t itf)
{
  uart_data_t *ud = &UART_DATA[itf];

  if (ud->uart_pos &&
      mutex_try_enter(&ud->uart_mtx, NULL))
  {
    uint32_t count;

    count = tud_cdc_n_write(itf, ud->uart_buffer, ud->uart_pos);
    if (count < ud->uart_pos)
      memmove(ud->uart_buffer, &ud->uart_buffer[count],
              ud->uart_pos - count);
    ud->uart_pos -= count;

    mutex_exit(&ud->uart_mtx);

    if (count)
      tud_cdc_n_write_flush(itf);
  }
}

void usb_cdc_process(uint8_t itf)
{
  usb_read_bytes(itf);
  usb_write_bytes(itf);
}

void core1_entry(void)
{
  board_init();
  // init device stack on configured roothub port
  tud_init(BOARD_TUD_RHPORT);

  if (board_init_after_tusb)
  {
    board_init_after_tusb();
  }

  while (1)
  {
    int itf;
    int con = 0;

    tud_task();

    for (itf = 0; itf < CFG_TUD_CDC; itf++)
    {
      if (tud_cdc_n_connected(itf))
      {
        con = 1;
        usb_cdc_process(itf);
      }
    }

    gpio_put(LED_PIN, con);
  }
}

void __not_in_flash_func(adc_capture)(uint16_t *buf, size_t count)
{
  adc_fifo_setup(true, false, 0, false, false);
  adc_run(true);
  for (size_t i = 0; i < count; i = i + 1)
    buf[i] = adc_fifo_get_blocking();
  adc_run(false);
  adc_fifo_drain();
}

// void sample(uint8_t *capture_buf) {
//   adc_fifo_drain();
//   adc_run(false);

//   dma_channel_configure(dma_chan, &cfg,
// 			capture_buf,    // dst
// 			&adc_hw->fifo,  // src
// 			NSAMP,          // transfer count
// 			true            // start immediately
// 			);

//   gpio_put(LED_PIN, 1);
//   adc_run(true);
//   dma_channel_wait_for_finish_blocking(dma_chan);
//   gpio_put(LED_PIN, 0);
// }

int main(void)
{
  int itf;

  gpio_init(LED_PIN);
  gpio_set_dir(LED_PIN, GPIO_OUT);
  for (int i = 0; i < 10; i++)
  {
    gpio_put(PICO_DEFAULT_LED_PIN, 1);
    sleep_ms(100);
    gpio_put(PICO_DEFAULT_LED_PIN, 0);
    sleep_ms(100);
  }

  stdio_init_all();
  adc_init();
  adc_set_temp_sensor_enabled(true);
  // Set all pins to input (as far as SIO is concerned)
  gpio_set_dir_all_bits(0);
  for (int i = 2; i < 30; ++i)
  {
    gpio_set_function(i, GPIO_FUNC_SIO);
    if (i >= 26)
    {
      gpio_disable_pulls(i);
      gpio_set_input_enabled(i, false);
    }
  }

  usbd_serial_init();

  multicore_launch_core1(core1_entry);

#define N_SAMPLES 512
  uint16_t sample_buf[N_SAMPLES];
  while (1)
  {
    if (tud_cdc_n_connected(0))
    {
      adc_capture(sample_buf, N_SAMPLES);
      tud_cdc_n_write(0, sample_buf, N_SAMPLES);
      tud_cdc_n_write(0, "\r\nabc\r\n", 7);
      tud_cdc_n_write_flush(0);
    }
  }

  return 0;
}
